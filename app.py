import streamlit as st
import pandas as pd
import datetime
from src.api.mercadolivre import MercadoLivreAPI
from src.api.amazon import AmazonAPI
import matplotlib.pyplot as plt

# Configuração da página
st.set_page_config(
    page_title="Dashboard - Grupo Vision",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inicializar session_state para armazenar dados e controlar primeira execução
if 'df_ml' not in st.session_state:
    st.session_state.df_ml = None
    
if 'first_run' not in st.session_state:
    st.session_state.first_run = True

st.sidebar.title("📊 Dash Vision")

today_side = datetime.datetime.now().strftime("%d/%m/%Y")
st.sidebar.caption(today_side)
st.sidebar.divider()

# Seletor de plataforma
plataforma = st.sidebar.selectbox(
    "Selecione a plataforma",
    ["Mercado Livre", "Amazon"],
    key="platform_selector"
)

# Função para carregar dados - ajustada para recarregar quando necessário
@st.cache_data(ttl=3600, show_spinner=False)
def carregar_dados_completos(_api, _inicio, _fim):
    # Convertendo datas para string para garantir formato consistente
    start_date = _inicio.strftime('%d/%m/%Y')
    end_date = _fim.strftime('%d/%m/%Y')

    print(f' Datas app.py -> Início: {start_date} - Fim: {end_date}')

    # Mercado Livre
    if _api == 'Mercado Livre':
        with st.spinner("Coletando dados do Mercado Livre..."):
            try:
                api_ml = MercadoLivreAPI()                
                salesDash = api_ml.generate_salesdash(start_date, end_date)
                return salesDash
            except Exception as e:
                st.error(f"Erro ML: {str(e)}")
                return None
    
    # Amazon
    else:
        with st.spinner("Coletando dados da Amazon..."):
            try:
                # Implementar a lógica da Amazon aqui
                pass
                return None  # Substitua pelo retorno real
            except Exception as e:
                st.error(f"Erro Amazon: {str(e)}")
                return None

def formatar_moeda_br(valor):
    try:
        # Garantir que estamos trabalhando com um float Python padrão
        valor_float = float(valor)
        
        # Formatar o número usando f-string
        valor_formatado = f"R$ {valor_float:,.2f}"
        
        # Ajustar para o padrão brasileiro (trocar . por , e vice-versa)
        valor_formatado = valor_formatado.replace(',', 'X').replace('.', ',').replace('X', '.')
        
        return valor_formatado
    except Exception as e:
        print(f"Erro ao formatar '{valor}' (tipo: {type(valor)}): {e}")
        return "R$ 0,00"
 
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    today = datetime.date.today()

    # Definir o período padrão (hoje e 7 dias atrás)
    default_start = today - datetime.timedelta(days=7)
    default_end = today

    # Definir os limites (1 ano atrás até hoje)
    min_date = today - datetime.timedelta(days=365)
    max_date = today

    # Criar o seletor de período com formato brasileiro
    periodo = st.date_input(
        "Selecione o período: ",
        (default_start, default_end),
        min_value=min_date,
        max_value=max_date,
        format="DD/MM/YYYY",  # Formato brasileiro
    )

# Carregar dados automaticamente na primeira execução
if st.session_state.first_run:
    with st.spinner("Carregando dados iniciais..."):
        st.session_state.df_ml = carregar_dados_completos(plataforma, default_start, default_end)
        st.session_state.first_run = False  # Marcar que não é mais a primeira execução

# Botão para recarregar dados com novo período
if st.button("🔄Carregar Dados", key="load_data_button"):
    # Verificar se o período é válido
    if len(periodo) == 2:
        data_inicial, data_final = periodo
        
        # Forçar recarga dos dados ao clicar no botão
        st.cache_data.clear()
        
        # Carregar os dados
        st.session_state.df_ml = carregar_dados_completos(plataforma, data_inicial, data_final)
        
        
# Processar e exibir dados se estiverem disponíveis
if st.session_state.df_ml is not None:
    df_ml = st.session_state.df_ml
        
    # Converter a coluna 'date' para datetime e manter apenas a data (sem hora)
    df_ml['date'] = pd.to_datetime(df_ml['date']).dt.date

    # Agrupar por data e SKU, somando as quantidades
    df_agrupado = df_ml.groupby(['date', 'sku'])[['qty', 'paid_amount_calculated_no_ship_cost']].sum().reset_index()

    # Calcular o acumulado (cumsum) para cada SKU separado
    df_agrupado['cumsum_qty'] = df_agrupado.groupby('sku')['qty'].cumsum()
    df_agrupado['cumsum_fat'] = df_agrupado.groupby('sku')['paid_amount_calculated_no_ship_cost'].cumsum()

    # Calcular o total de vendas por SKU para o ranking (Quantidade)
    total_vendas_por_sku = df_ml.groupby('sku')['qty'].sum().reset_index()
    total_vendas_por_sku = total_vendas_por_sku.sort_values('qty', ascending=False)

    # Calcular o faturamento total por SKU para o ranking 
    total_fat_vendas_por_sku = df_ml.groupby('sku')['paid_amount_calculated_no_ship_cost'].sum().reset_index()
    total_fat_vendas_por_sku = total_fat_vendas_por_sku.sort_values('paid_amount_calculated_no_ship_cost', ascending=False)

    # Identificar os top SKUs por quantidade e faturamento
    top_skus = total_vendas_por_sku.head(5)['sku'].tolist()
    top_skus_fat = total_fat_vendas_por_sku.head(5)['sku'].tolist()

    # Filtrar apenas os top SKUs para o gráfico
    df_top_skus = df_agrupado[df_agrupado['sku'].isin(top_skus)] # Quantidade
    df_top_skus_fat = df_agrupado[df_agrupado['sku'].isin(top_skus_fat)] # Financeiro

    # Pivotar os dados para o formato esperado pelo st.line_chart - top 5
    df_pivot = df_top_skus.pivot(index='date', columns='sku', values='qty')
    df_pivot_fat = df_top_skus_fat.pivot(index='date', columns='sku', values='paid_amount_calculated_no_ship_cost')

    # Pivotar os dados, com a soma acumulada para o gráfico - top 5
    df_pivot_cumsum = df_top_skus.pivot(index='date', columns='sku', values='cumsum_qty')
    df_pivot_cumsum_fat = df_top_skus_fat.pivot(index='date', columns='sku', values='cumsum_fat')

    # Pivotar os dados para o formato esperado pelo st.line_chart - todos os produtos
    df_pivot_todos = df_agrupado.pivot(index='date', columns='sku', values='qty')
    df_pivot_fat_todos = df_agrupado.pivot(index='date', columns='sku', values='paid_amount_calculated_no_ship_cost')

    # Pivotar os dados com a soma acumulada para o gráfico - todos os produtos
    df_pivot_cumsum_todos = df_agrupado.pivot(index='date', columns='sku', values='cumsum_qty')
    df_pivot_cumsum_fat_todos = df_agrupado.pivot(index='date', columns='sku', values='cumsum_fat')

    # Função para plotar gráfico com matplotlib e exibir no Streamlit
    def plot_matplotlib(df, ylabel, height=400):
        fig, ax = plt.subplots(figsize=(10, height/100))
        df_plot = df.copy()
        df_plot.index = pd.to_datetime(df_plot.index)
        df_plot = df_plot.sort_index()
        for col in df_plot.columns:
            ax.plot(df_plot.index, df_plot[col], marker='o', label=str(col))
        ax.set_ylabel(ylabel)
        ax.set_xlabel('Data')
        ax.set_xticks(df_plot.index)
        ax.set_xticklabels([x.strftime('%d/%m/%y') for x in df_plot.index], rotation=45, ha='right')
        ax.legend(title='SKU', bbox_to_anchor=(1.05, 1), loc='upper left')
        plt.tight_layout()
        st.pyplot(fig)

    tab1, tab2, tab3 = st.tabs(["Skus Quantidade", "Skus Faturamento (R$)", "Dataframe"])
    with tab1:
        cl1, cl2, cl3 = st.columns([2, 1, 1])
        with cl1:
            st.subheader(f"Total Geral: **:green[{total_vendas_por_sku['qty'].sum()}]**")
            
        with cl3:        
            exibir_top5 = st.toggle("Exibir Top 5 - Nº Vendas", value=True)
            exibir_vendas_acum = st.toggle("Exibir Vendas Acumuladas por Dia")    
                    
        st.write("")

        if exibir_vendas_acum and exibir_top5:
            plot_matplotlib(df_pivot_cumsum, 'Qtd. Acumulada', height=400)
        elif exibir_vendas_acum and not exibir_top5:    
            plot_matplotlib(df_pivot_cumsum_todos, 'Qtd. Acumulada', height=400)
        elif not exibir_vendas_acum and exibir_top5:
            plot_matplotlib(df_pivot, 'Qtd. Vendida', height=400)
        else:    
            plot_matplotlib(df_pivot_todos, 'Qtd. Vendida', height=400)

        # Adicionar o ranking com troféus
        st.subheader("Ranking Final")
        
        # Criar colunas para o layout do ranking
        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            if exibir_top5:
                ranking = total_vendas_por_sku.head(5)
            else:
                ranking = total_vendas_por_sku  

            for i, (index, row) in enumerate(ranking.iterrows()):
                sku = row['sku']
                quantidade = row['qty']
                
                # Adicionar troféu para os 3 primeiros
                if i == 0:
                    st.markdown(f"### 🏆 1º Lugar: {sku} - {quantidade} unidades")
                elif i == 1:
                    st.markdown(f"### 🥈 2º Lugar: {sku} - {quantidade} unidades")
                elif i == 2:
                    st.markdown(f"### 🥉 3º Lugar: {sku} - {quantidade} unidades")
                else:
                    st.markdown(f"### {i+1}º Lugar: {sku} - {quantidade} unidades")
                
                # Adicionar barra de progresso para visualização
                max_qty = total_vendas_por_sku.iloc[0]['qty']  # Quantidade do primeiro colocado
                progress = quantidade / max_qty
                st.progress(progress)

    with tab2:
        cl1, cl2, cl3 = st.columns([2, 1, 1])
        with cl1:
            total_fat = formatar_moeda_br(total_fat_vendas_por_sku['paid_amount_calculated_no_ship_cost'].sum())
            st.subheader(f"Total Geral: **:green[{total_fat}]**")
                
        with cl3:        
            exibir_top5_fat = st.toggle("Exibir Top 5 - Faturamento", value=True)
            exibir_vendas_acum_fat = st.toggle("Exibir Faturamento Acumulado por Dia")
                    
        st.write("")    

        if exibir_vendas_acum_fat and exibir_top5_fat:
            plot_matplotlib(df_pivot_cumsum_fat, 'Faturamento Acumulado', height=400)
        elif exibir_vendas_acum_fat and not exibir_top5_fat:    
            plot_matplotlib(df_pivot_cumsum_fat_todos, 'Faturamento Acumulado', height=400)
        elif not exibir_vendas_acum_fat and exibir_top5_fat:
            plot_matplotlib(df_pivot_fat, 'Faturamento', height=400)
        else:    
            plot_matplotlib(df_pivot_fat_todos, 'Faturamento', height=400)

        # Adicionar o ranking com troféus
        st.subheader("Ranking Final")
        
        # Criar colunas para o layout do ranking
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            if exibir_top5_fat:
                ranking_fat = total_fat_vendas_por_sku.head(5)
            else:
                ranking_fat = total_fat_vendas_por_sku        

            # Obter os 5 primeiros SKUs com suas quantidades totais
            for i, (index, row) in enumerate(ranking_fat.iterrows()):
                sku = row['sku']            
                faturamento = row['paid_amount_calculated_no_ship_cost']
                
                # Adicionar troféu para os 3 primeiros
                if i == 0:
                    st.markdown(f"### 🏆 1º Lugar: {sku} - {formatar_moeda_br(faturamento)}")
                elif i == 1:
                    st.markdown(f"### 🥈 2º Lugar: {sku} - {formatar_moeda_br(faturamento)}")
                elif i == 2:
                    st.markdown(f"### 🥉 3º Lugar: {sku} - {formatar_moeda_br(faturamento)}")
                else:
                    st.markdown(f"### {i+1}º Lugar: {sku} - {formatar_moeda_br(faturamento)}")
                
                # Adicionar barra de progresso para visualização
                max_fat = total_fat_vendas_por_sku.iloc[0]['paid_amount_calculated_no_ship_cost']  # Faturamento do primeiro colocado
                progress = faturamento / max_fat
                st.progress(progress)

    with tab3:
        # Exibir a coluna de data formatada como dd/mm/yy apenas no DataFrame
        df_ml_exibe = df_ml.copy()
        df_ml_exibe['date'] = df_ml_exibe['date'].apply(lambda x: x.strftime('%d/%m/%y'))
        st.dataframe(df_ml_exibe, height=250, use_container_width=True)

elif st.session_state.df_ml is None and not st.session_state.first_run:
    st.warning("Falha ao carregar os dados. Por favor, verifique o período selecionado e tente novamente.")