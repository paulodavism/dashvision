import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone
import os
import sys
import logging
from sqlmodel import Session, select, delete
from sqlalchemy import func, and_

# Configurações iniciais
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.mercadolivre import MercadoLivreAPI
from src.api.amazon import AmazonAPI
from src.api.mercos import MercosWebScraping
from src.db.database import DatabaseManager
from src.db.models import EstoqueMercos, ConciliacaoMercos

# Configuração de logging
logging.basicConfig(level=logging.DEBUG)

# Configuração da página
st.set_page_config(
    page_title="DV SmartShop - Gestão Integrada de Estoque",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Constantes
DATE_FORMAT = "%Y-%m-%d %H:%M"
COLOR_SCHEME = {
    'Mercado Livre (Full)': '#FFFF00',
    'Amazon (FBA)': '#FF6B6B',    
    'background': '#F8F9FA'
}

# Cores para depósitos próprios
DEPOSITO_COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf'
]

def gerar_paleta_depositos(depositos):
    """Gera cores únicas para cada depósito próprio"""
    return {dep.nome: DEPOSITO_COLORS[i % len(DEPOSITO_COLORS)] for i, dep in enumerate(depositos)}

st.cache_data.clear()
st.cache_resource.clear()

def setup_environment():
    """Configuração visual do ambiente"""
    st.markdown(f"""
    <style>
        .metric-card {{
            background: {COLOR_SCHEME['background']};
            border-radius: 10px;
            padding: 20px;
            margin: 10px 0;
        }}
        .stDataFrame {{ 
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            border-radius: 8px;
        }}
        .refresh-button {{
            background: #4CAF50 !important;
            color: white !important;
        }}
    </style>
    """, unsafe_allow_html=True)

def formatar_numero(valor):
    """
    Formata um número inteiro ou float para usar o ponto como separador de milhar.
    
    Args:
        valor (int ou float): O número a ser formatado.
    
    Returns:
        str: O número formatado como string.
    """
    try:
        if isinstance(valor, (int, float)):
            return f"{valor:,}".replace(",", ".")  # Substitui vírgula por ponto
        else:
            return str(valor)  # Retorna como string se não for numérico
    except Exception:
        return str(valor)  # Fallback para qualquer erro    


def carregar_estoque_interno():
    """
    Carrega os dados de estoque interno do banco de dados e concilia com os SKUs do Mercado Livre
    
    Returns:
        pd.DataFrame: Um DataFrame contendo os dados de estoque interno, com colunas padronizadas.
    """
    try:
        # Carrega os dados do Mercos do banco de dados
        with Session(DatabaseManager().engine) as session:
            # Busca os dados mais recentes de estoque
            query = select(EstoqueMercos).order_by(EstoqueMercos.data_atualizacao.desc())
            resultados = session.exec(query).all()
            
            # Converte os resultados para um DataFrame
            df_mercos = pd.DataFrame([{
                'SKU': item.sku,
                'Produto': item.produto,
                'Depósito': item.deposito,
                'Estoque': item.quantidade
            } for item in resultados])
            
            if df_mercos.empty:
                return pd.DataFrame()
            
            # Busca as conciliações existentes
            query_conciliacoes = select(ConciliacaoMercos)
            conciliacoes = session.exec(query_conciliacoes).all()
            
            # Converte as conciliações para um DataFrame
            df_conciliacoes = pd.DataFrame([{
                'sku_mercos': item.sku_mercos,
                'sku_ml_amazon': item.sku_ml_amazon,
                'produto': item.produto,
                'deposito_mercos': item.deposito_mercos,
                'estoque_mercos': item.estoque_mercos
            } for item in conciliacoes])
            
            if df_conciliacoes.empty:
                return pd.DataFrame()
            
            # 1. Filtrar linhas onde 'sku_ml_amazon' está preenchida
            df_filtrado = df_conciliacoes[df_conciliacoes['sku_ml_amazon'].notna() & (df_conciliacoes['sku_ml_amazon'] != '')].copy()
            
            # 2. Padronizar nomes das colunas
            df_filtrado.rename(columns={'sku_ml_amazon': 'SKU',
                                    'produto': 'Produto',
                                    'deposito_mercos': 'Depósito',
                                    'estoque_mercos': 'Estoque'}, inplace=True)
            
            # 3. Verificar se houve atualização de estoque
            for index_mercos, reg_mercos in df_mercos.iterrows():
                for index_conciliado, reg_conciliado in df_filtrado.iterrows():
                    if reg_mercos['SKU'] == reg_conciliado['sku_mercos']:
                        if reg_mercos['Estoque'] != reg_conciliado['Estoque']:
                            df_filtrado.loc[index_conciliado, 'Estoque'] = reg_mercos['Estoque']
                            print(f"Estoque do produto {reg_conciliado['Produto']} atualizado de {reg_conciliado['Estoque']} para {reg_mercos['Estoque']}.", flush=True)
            
            # 4. Selecionar apenas as colunas desejadas
            df_estoque = df_filtrado[['SKU', 'Produto', 'Depósito', 'Estoque']]
            
            return df_estoque
        
    except Exception as e:
        print(f"Erro ao carregar estoque interno: {str(e)}")
        return pd.DataFrame()  # Retorna um DataFrame vazio em caso de erro


def criar_card_metrica(titulo, valor, ajuda=None):
    """Componente de métrica estilizado"""
    return f"""
    <div style="border: 1px solid #ddd; border-radius: 8px; padding: 16px; text-align: center; background-color: white;">
        <h3 style="color: black;">{titulo}</h3>
        <p style="font-size: 24px; font-weight: bold; color: black;">{valor}</p>
        {f'<p style="font-size: 12px; color: gray;">{ajuda}</p>' if ajuda else ''}
    </div>
    """

@st.cache_data(ttl=3600, show_spinner=False)
def carregar_dados_completos(_apis):
    """Combina estoque de marketplaces com estoque próprio"""
    # Dados externos
    dados_externos = []
    
    # Mercado Livre
    with st.spinner("Coletando Mercado Livre..."):
        try:
            ml_data = _apis['ml'].gerar_relatorio_estoque()
            if not ml_data.empty:
                ml_data.rename(columns={"Nome": "Produto"}, inplace=True)  # Padroniza nome da coluna
                ml_data['Depósito'] = 'Mercado Livre (Full)'
                dados_externos.append(ml_data)

        except Exception as e:
            st.error(f"Erro ML: {str(e)}")
    
    # Amazon
    with st.spinner("Coletando Amazon..."):
        try:
            amazon_data = _apis['amazon'].gerar_relatorio_estoque()
            if not amazon_data.empty:
                amazon_data.rename(columns={"Nome": "Produto"}, inplace=True)  # Padroniza nome da coluna
                amazon_data['Depósito'] = 'Amazon (FBA)'
                dados_externos.append(amazon_data)
        except Exception as e:
            st.error(f"Erro Amazon: {str(e)}")
    
    # Dados internos
    with st.spinner("Carregando estoque próprio..."):
        interno_df = carregar_estoque_interno()
    
    # Combinação
    externo_df = pd.concat(dados_externos, ignore_index=True) if dados_externos else pd.DataFrame()
    return pd.concat([externo_df, interno_df], ignore_index=True)


def exibir_visao_integrada(apis):
    """Dashboard principal com dados combinados"""
    st.title("📊 Visão Integrada de Estoque")
    st.caption(f"Última atualização: {datetime.now().strftime(DATE_FORMAT)}")
    
    # Inicializa o estado da sessão para controlar o carregamento inicial dos dados
    if 'dados_carregados' not in st.session_state:
        st.session_state.dados_carregados = False

    # Carregamento de dados
    if not st.session_state.dados_carregados or st.session_state.get('atualizar_dados', False):
        with st.spinner("Carregando dados..."):
            df_completo = carregar_dados_completos(apis)
            st.session_state.df_completo = df_completo  # Armazena o DataFrame no estado da sessão
            st.session_state.dados_carregados = True
            st.session_state.atualizar_dados = False  # Reseta o flag
    else:
        df_completo = st.session_state.df_completo  # Recupera o DataFrame do estado da sessão
        
    if df_completo.empty:
        st.warning("Nenhum dado disponível")
        return
    
    # Filtragem das colunas padronizadas
    df_completo = df_completo[['SKU', 'Produto', 'Depósito', 'Estoque']]
    
    # Filtros
    with st.sidebar:

        st.markdown("---")
        if st.button("🔄 Atualizar Dados", help="Atualizar dados de todos os depósitos", use_container_width=True):
            carregar_dados_completos.clear() 
            st.session_state.atualizar_dados = True
            st.rerun()

        st.header("🔍 Filtros Avançados")
        filtro_deposito = st.multiselect(
            "Depósitos",
            options=df_completo['Depósito'].unique(),
            default=[]
        )
        
        filtro_sku = st.multiselect(
            "SKUs",
            options=df_completo['SKU'].unique(),
            default=[]
        )
    
    # Aplicar filtros
    df_filtrado = df_completo.copy()
    if filtro_deposito:
        df_filtrado = df_filtrado[df_filtrado['Depósito'].isin(filtro_deposito)]
    if filtro_sku:
        df_filtrado = df_filtrado[df_filtrado['SKU'].isin(filtro_sku)]


    # Métricas
    cols = st.columns(3)
    metricas = [
        ("Depósitos", df_filtrado['Depósito'].nunique(), "Total de locais"),
        ("SKUs Únicos", formatar_numero(df_filtrado['SKU'].nunique()), "Produtos diferentes"),
        ("Estoque Total", formatar_numero(df_filtrado['Estoque'].sum()), "Unidades totais")
    ]

    for col, (titulo, valor, ajuda) in zip(cols, metricas):
        col.markdown(criar_card_metrica(titulo, valor, ajuda), unsafe_allow_html=True)    

    
    # Visualizações
    st.markdown("---")
    visao_selecionada = st.radio(
        "Tipo de Visualização:",
        ["📈 Por SKU", "📊 Distribuição", "🗃️ Dados Brutos"],
        horizontal=True,
        label_visibility="collapsed"
    )

    # Gerar paleta dinâmica
    depositos_proprios = [dep for dep in df_completo['Depósito'].unique() if dep not in ['Mercado Livre (Full)', 'Amazon (FBA)']]
    paleta_dinamica = {
        dep: cor for dep, cor in gerar_paleta_depositos([type('obj', (object,), {'nome': dep}) for dep in depositos_proprios]).items()
    }
    paleta_dinamica.update(COLOR_SCHEME)  # Mantém cores fixas para marketplaces

    
    if visao_selecionada == "📈 Por SKU":
        # Agrupar os dados por SKU e Depósito
        df_grouped = df_filtrado.groupby(['SKU', 'Depósito'])['Estoque'].sum().reset_index()

        # Ordena os dados por estoque em ordem decrescente
        df_grouped = df_grouped.sort_values(by='Estoque', ascending=False)

        fig = px.bar(
            df_grouped,
            x='SKU',
            y='Estoque',
            color='Depósito',
            color_discrete_map=paleta_dinamica,
            barmode='group',
            height=600,
            text_auto=True,
            labels={'Estoque': 'Quantidade em Estoque', 'SKU': 'SKU do Produto'} # Melhora os rótulos
        )

        fig.update_layout(
            xaxis_title="SKU do Produto",
            yaxis_title="Quantidade em Estoque",
            title="Distribuição de Estoque por SKU",
            xaxis={'categoryorder':'total descending'}, # Ordena por valor total
            xaxis_tickangle=-45  # Rotaciona os rótulos do eixo X para melhor legibilidade
        )

        st.plotly_chart(fig, use_container_width=True)
    
    elif visao_selecionada == "📊 Distribuição":
        fig = px.pie(
            df_filtrado.groupby('Depósito')['Estoque'].sum().reset_index(),
            names='Depósito',
            values='Estoque',
            color='Depósito',
            color_discrete_map=paleta_dinamica
        )
        st.plotly_chart(fig, use_container_width=True)
        

    else:
        # Converte todas as colunas do tipo int64 para int padrão do Python
        df_filtrado = df_filtrado.astype({col: 'int' for col in df_filtrado.select_dtypes(include=['int64']).columns}).set_index("SKU")

        # Ordena os dados por estoque em ordem decrescente
        df_filtrado = df_filtrado.sort_values(by='Estoque', ascending=False)

        # Garante que o valor máximo seja um int padrão do Python
        max_estoque = int(df_filtrado['Estoque'].max())

        st.dataframe(
            df_filtrado,
            column_config={
                "Estoque": st.column_config.ProgressColumn(
                    "Estoque",
                    format="%d",  # Usa %d para inteiros
                    min_value=0,
                    max_value=max_estoque
                ),
            },
            use_container_width=True,
            height=1200
        )

def limpar_cache():
    """Limpa o cache do Streamlit"""
    st.cache_data.clear()
    st.cache_resource.clear()

def reset_estado_estoque():
    """Reseta as variáveis de estado da tela de Gestão de Estoque."""
    for key in ['etapa', 'produtos_selecionados', 'deposito_nome', 'tipo', 'origem_nome', 'destino_nome']:
        if key in st.session_state:
            del st.session_state[key]


def exibir_gestao_estoque():
    st.header("📦 Gestão de Estoque")
    
    # Exibir mensagens de sucesso, se houver
    if getattr(st.session_state, "mensagem_sucesso", None):
        st.toast(st.session_state.mensagem_sucesso, icon="✅")
        del st.session_state.mensagem_sucesso

    # Menu lateral para navegar entre as funcionalidades
    menu_opcao = st.sidebar.selectbox(
        "Selecione uma operação",
        ["Consultar Estoque Próprio", "Conciliar SKUs"],
    )

    # Verifica se o menu foi alterado e reseta o estado 
    if st.session_state.get('menu_opcao_anterior') != menu_opcao:
        reset_estado_estoque()
        if 'historico' in st.session_state:
            del st.session_state['historico']
        st.session_state.menu_opcao_anterior = menu_opcao
    
    def atualizar_dados_mercos():
        """Executa a raspagem de dados do Mercos"""
        mercos_rasp = MercosWebScraping()
        return mercos_rasp.carrega_dados_mercos()
    
    def exibir_tabela_mercos():
        """Exibe a tabela de estoque do Mercos lendo dados do banco de dados"""
        try:
            # Inicializa o gerenciador do banco de dados
            db_manager = DatabaseManager()
            
            # Cria uma sessão do banco de dados
            with Session(db_manager.engine) as session:
                # Busca os dados mais recentes de estoque
                query = select(EstoqueMercos).order_by(EstoqueMercos.data_atualizacao.desc())
                resultados = session.exec(query).all()
                
                # Converte os resultados para um DataFrame
                dados = []
                for item in resultados:
                    dados.append({
                        'SKU': item.sku,
                        'Produto': item.produto,
                        'Depósito': item.deposito,
                        'Estoque': item.quantidade
                    })
                
                df_estoque_mercos = pd.DataFrame(dados).set_index("SKU")
                
                if df_estoque_mercos.empty:
                    st.warning("Nenhum dado de estoque encontrado no banco de dados.")
                    return
                
                # Garante que a coluna 'Estoque' seja numérica
                df_estoque_mercos['Estoque'] = pd.to_numeric(df_estoque_mercos['Estoque'], errors='coerce')

                # Ordena os dados por estoque em ordem decrescente
                df_estoque_mercos = df_estoque_mercos.sort_values(by='Estoque', ascending=False)
                
                # Garante que o valor máximo seja um int padrão do Python
                max_estoque_mercos = int(df_estoque_mercos['Estoque'].max())

                st.dataframe(
                    df_estoque_mercos,
                    column_config={
                        "Estoque": st.column_config.ProgressColumn(
                            "Estoque",
                            format="%d",  # Usa %d para inteiros
                            min_value=0,
                            max_value=max_estoque_mercos
                        ),
                    },
                    use_container_width=True,
                    height=600
                )
                
        except Exception as e:
            st.error(f"Erro ao carregar dados do banco de dados: {str(e)}")

    def ler_data_processamento():
        """Lê a data da última atualização do banco de dados"""
        try:
            with Session(DatabaseManager().engine) as session:
                # Busca a data mais recente de atualização
                ultima_atualizacao = session.exec(
                    select(EstoqueMercos.data_atualizacao)
                    .order_by(EstoqueMercos.data_atualizacao.desc())
                    .limit(1)
                ).first()
                
                if ultima_atualizacao:
                    # Ajusta o timezone subtraindo 3 horas
                    data_ajustada = ultima_atualizacao - pd.Timedelta(hours=3)
                    return data_ajustada.strftime('%d/%m/%Y %H:%M')
                return "Processamento ainda não realizado."
                
        except Exception as e:
            logging.error(f"Erro ao ler data de processamento: {str(e)}")
            return "Erro ao ler data de processamento"
            
    if menu_opcao == "Consultar Estoque Próprio":
        st.subheader("🔍 Consultar Estoque Próprio (Mercos)")                        
        st.info(f"Última atualização de processamento: {ler_data_processamento()}")
        st.markdown("---")

        # Inicializa o estado da sessão
        if "confirmacao_ativa" not in st.session_state:
            st.session_state.confirmacao_ativa = False

        # Botão principal para iniciar o processo de atualização
        if st.button("🔄 Atualizar Dados", help="Obter dados do sistema Mercos"):
            st.session_state.confirmacao_ativa = True

        # Exibe a mensagem de confirmação se a flag estiver ativa
        if st.session_state.confirmacao_ativa:
            confirm_container = st.empty()
            
            with confirm_container.container():
                st.warning("Atenção! Este processo pode levar alguns minutos. Confirma a operação?")
                col1, col2 = st.columns([1, 25])
                confirmar = col1.button("Sim", key="confirmar_atualizacao")
                cancelar = col2.button("Não", key="cancelar_atualizacao")
            
            if confirmar:
                confirm_container.empty()            
                with st.spinner("Coletando dados do sistema Mercos..."):
                    try:
                        atualizar_dados_mercos()                         
                        st.toast("Dados atualizados com sucesso!", icon="✅")     
                    except Exception as e:
                        st.error(f"Erro ao atualizar os dados do Mercos: {str(e)}")                    
                st.session_state.confirmacao_ativa = False
                st.rerun()
            
            elif cancelar:
                confirm_container.empty()
                st.session_state.confirmacao_ativa = False
                st.rerun()
                                                                
        exibir_tabela_mercos()

    elif menu_opcao == "Conciliar SKUs":
        st.subheader("🔄 Conciliação de Produtos")
        
        # Carregar dados do Mercado Livre como referência
        try:
            # Verifica se os dados já foram carregados
            if 'df_completo' not in st.session_state:
                st.error("Por favor, acesse primeiro a visão integrada para carregar os dados do Mercado Livre.")
                st.stop()
            
            # Filtra apenas os dados do Mercado Livre
            skus_referencia = st.session_state.df_completo[
                st.session_state.df_completo['Depósito'] == 'Mercado Livre (Full)'
            ].copy()
            
            if skus_referencia.empty:
                st.error("Não foi possível obter os SKUs de referência do Mercado Livre. Tente atualizar os dados primeiro.")
                st.stop()
            
            # Garante que não há duplicatas nos SKUs de referência
            skus_referencia = skus_referencia.drop_duplicates(subset=['SKU'])
            #st.info(f"Total de SKUs disponíveis para conciliação: {len(skus_referencia)}")
        except Exception as e:
            st.error(f"Erro ao carregar dados do Mercado Livre: {str(e)}")
            st.stop()
        
        # Carregar os produtos do Mercos do banco de dados
        try:
            with Session(DatabaseManager().engine) as session:
                query = select(EstoqueMercos).order_by(EstoqueMercos.data_atualizacao.desc())
                resultados = session.exec(query).all()
                
                # Converte os resultados para um DataFrame
                produtos_mercos = pd.DataFrame([{
                    'SKU': item.sku,
                    'Produto': item.produto,
                    'Depósito': item.deposito,
                    'Estoque': item.quantidade
                } for item in resultados])
                
                if produtos_mercos.empty:
                    st.error("Nenhum produto encontrado no Mercos. Execute primeiro a atualização do estoque próprio.")
                    st.stop()
                    
                #st.info(f"Total de produtos do Mercos: {len(produtos_mercos)}")
                
        except Exception as e:
            st.error(f"Erro ao carregar dados do Mercos: {str(e)}")
            st.stop()
        
        # Carregar conciliações existentes do banco de dados
        try:
            with Session(DatabaseManager().engine) as session:
                query = select(ConciliacaoMercos)
                resultados = session.exec(query).all()
                
                # Converte os resultados para um DataFrame
                produtos_conciliados = pd.DataFrame([{
                    'sku_mercos': item.sku_mercos,
                    'sku_ml_amazon': item.sku_ml_amazon,
                    'produto': item.produto,
                    'deposito_mercos': item.deposito_mercos,
                    'estoque_mercos': item.estoque_mercos
                } for item in resultados])
                
                #st.info(f"Total de produtos já conciliados: {len(produtos_conciliados)}")
                
        except Exception as e:
            st.error(f"Erro ao carregar conciliações: {str(e)}")
            # Cria um DataFrame vazio com as colunas necessárias
            produtos_conciliados = pd.DataFrame(columns=[
                "sku_mercos", "sku_ml_amazon", "produto", "deposito_mercos", "estoque_mercos"
            ])
            st.info("Nenhuma conciliação existente. Iniciando do zero.")
        
        # Mescla os DataFrames com base nas colunas correspondentes
        if not produtos_conciliados.empty:
            produtos_mercos = produtos_mercos.merge(
                produtos_conciliados[["sku_mercos", "sku_ml_amazon"]],
                left_on="SKU",
                right_on="sku_mercos",
                how="left"
            )
        else:
            # Se não houver conciliações, adiciona a coluna sku_ml_amazon vazia
            produtos_mercos["sku_ml_amazon"] = ""
        
        # Preenche os valores ausentes com strings vazias
        produtos_mercos["sku_ml_amazon"] = produtos_mercos["sku_ml_amazon"].fillna("")
        
        # Filtro aplicado para visualizar: Todos, Conciliados ou Não Conciliados
        filtro_status = st.selectbox("Filtrar por:", ["Todos", "Conciliados", "Não Conciliados"])
        
        # Aplica o filtro
        if filtro_status == "Conciliados":
            df_form = produtos_mercos[produtos_mercos["sku_ml_amazon"].str.strip() != ""].copy()
        elif filtro_status == "Não Conciliados":
            df_form = produtos_mercos[produtos_mercos["sku_ml_amazon"].str.strip() == ""].copy()
        else:
            df_form = produtos_mercos.copy()
        
        # Totalizadores
        total_mercos = len(produtos_mercos)
        total_conciliados = len(produtos_mercos[produtos_mercos["sku_ml_amazon"].str.strip() != ""])
        total_nao_conciliados = total_mercos - total_conciliados
        st.info(f"Total Produtos Mercos: {total_mercos} | Conciliados: {total_conciliados} | Não Conciliados: {total_nao_conciliados}")
        
        with st.form("conciliacao_form"):
            conciliacoes = []
            skus_online_selecionados = []  # Garante que cada SKU online seja escolhida apenas uma vez
            
            for idx, row in df_form.iterrows():
                # Dividindo a linha em 4 colunas:
                col_fisico_sku, col_fisico_prod, col_online_sku, col_online_prod = st.columns(4)
                
                with col_fisico_sku:
                    st.text_input("SKU Mercos", value=row["SKU"], disabled=True, key=f"fisico_sku_{idx}")
                with col_fisico_prod:
                    st.text_input("Produto Mercos", value=row["Produto"], disabled=True, key=f"fisico_prod_{idx}")
                
                # Lista de SKUs já conciliados (excluindo o SKU atual, se existir)
                skus_conciliados = produtos_conciliados["sku_ml_amazon"].tolist() if not produtos_conciliados.empty else []
                if row["sku_ml_amazon"] != "":
                    skus_conciliados.remove(row["sku_ml_amazon"])
                
                # Lista de SKUs disponíveis para conciliação
                skus_disponiveis = skus_referencia[~skus_referencia["SKU"].isin(skus_conciliados)]["SKU"].tolist()
                
                # Adiciona o SKU atual (se existir) e a opção vazia
                available_options = [""] + [row["sku_ml_amazon"]] if row["sku_ml_amazon"] != "" else [""]
                available_options += skus_disponiveis
                
                # Remove duplicatas e garante a ordem
                available_options = list(dict.fromkeys([opt.strip() for opt in available_options]))
                
                # Converte explicitamente para string para evitar ambiguidade
                sku_mercos_val = str(row["sku_ml_amazon"])
                
                label_online = "SKU Online" + (" ✅" if sku_mercos_val != "" else "")
                with col_online_sku:
                    # Use st.session_state para armazenar o valor selecionado
                    key_online_sku = f"online_sku_{idx}"
                    
                    # Obtém o valor do st.session_state, se existir, senão usa o valor da linha
                    default_value = st.session_state.get(key_online_sku, row["sku_ml_amazon"] if row["sku_ml_amazon"] in available_options else "")
                    
                    sku_online = st.selectbox(
                        label_online,
                        options=available_options,
                        index=available_options.index(default_value) if default_value in available_options else 0,
                        key=key_online_sku
                    )
                    
                    # Remove espaços em branco do valor selecionado
                    sku_online = sku_online.strip()
                    
                if sku_online != "":
                    skus_online_selecionados.append(sku_online)
                
                # Auto-preenche o Produto Online, caso um SKU seja selecionado
                try:
                    produto_online = skus_referencia.loc[skus_referencia["SKU"] == sku_online, "Produto"].iloc[0] if sku_online != "" else ""
                except IndexError:
                    produto_online = ""
                with col_online_prod:
                    st.text_input("Produto Online", value=str(produto_online), disabled=True, key=f"online_prod_{idx}")
                
                conciliacoes.append({
                    "sku_mercos": row["SKU"],
                    "sku_ml_amazon": sku_online,
                    "produto": row["Produto"],
                    "deposito_mercos": row["Depósito"],
                    "estoque_mercos": row["Estoque"]
                })
            
            submitted = st.form_submit_button("💾 Salvar Conciliação")
        
        if submitted:
            try:
                with Session(DatabaseManager().engine) as session:
                    # Remove conciliações existentes para os SKUs que foram atualizados
                    skus_atualizados = [c["sku_mercos"] for c in conciliacoes]
                    if skus_atualizados:
                        # Usa delete() do SQLModel para remover registros
                        session.exec(
                            delete(ConciliacaoMercos).where(ConciliacaoMercos.sku_mercos.in_(skus_atualizados))
                        )
                    
                    # Adiciona as novas conciliações
                    for conciliacao in conciliacoes:
                        if conciliacao["sku_ml_amazon"]:  # Só adiciona se tiver SKU online
                            nova_conciliacao = ConciliacaoMercos(**conciliacao)
                            session.add(nova_conciliacao)
                    
                    session.commit()
                    st.success("✅ Conciliação concluída com sucesso!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Erro ao salvar conciliações: {str(e)}")
                session.rollback()


def main():
    setup_environment()
    
    # Menu principal
    with st.sidebar:
        st.header("📦 Menu Principal")
        opcao = st.radio(
            "Selecione o módulo:",
            ["Dashboard - Visão Integrada de Estoque", "Gestão Estoque Próprio"],
            index=0
        )
                            
    # Controle de exibição
    if opcao == "Dashboard - Visão Integrada de Estoque":
        apis = {
            'ml': MercadoLivreAPI(),
            'amazon': AmazonAPI()
        }
        exibir_visao_integrada(apis)
    elif opcao == "Gestão Estoque Próprio":
        exibir_gestao_estoque()     

if __name__ == "__main__":
    main()