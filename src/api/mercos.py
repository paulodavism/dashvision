from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import os
from dotenv import load_dotenv
import pandas as pd
import time
import logging
import platform
import sys
from pathlib import Path

# Adiciona o diretório raiz ao PYTHONPATH
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.db.database import DatabaseManager

# Configurar o logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MercosWebScraping:
    def __init__(self):
        self.df_filtrado = pd.DataFrame()
        self._setup_chrome_options()

    def _setup_chrome_options(self):
        """Configura as opções do Chrome de forma compatível com Windows e Linux"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # User agent específico para cada sistema operacional
        if platform.system() == "Windows":
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        else:
            chrome_options.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
        self.chrome_options = chrome_options

    def _login(self, driver):
        """Realiza o login no Mercos"""
        try:
            driver.get("https://app.mercos.com/login")
            
            email = os.getenv("MERCOS_EMAIL")
            senha = os.getenv("MERCOS_SENHA")

            if not email or not senha:
                logger.error("Credenciais ausentes ou inválidas")
                return False

            # Preencher credenciais
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "id_usuario"))
            ).send_keys(email)
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "id_senha"))
            ).send_keys(senha)

            # Clicar no botão de login
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "botaoEfetuarLogin"))
            ).click()

            # Verificar login bem-sucedido
            WebDriverWait(driver, 20).until(
                EC.url_contains("/327426/indicadores/")
            )
            logger.info("Login realizado com sucesso!")
            return True

        except TimeoutException as e:
            logger.error(f"Erro no login: {e}")
            return False

    def _navegar_para_produtos(self, driver):
        """Navega para a página de produtos"""
        try:
            PRODUTOS_URL = "https://app.mercos.com/industria/327426/produtos/"
            driver.get(PRODUTOS_URL)
            
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#listagem_produto"))
            )
            logger.info("Acesso à página de produtos realizado!")

            # === APLICAR FILTRO "TODOS OS PRODUTOS" ===
            try:
                # Abrir o dropdown do filtro
                filtro_dropdown = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, ".Botao__botao___U8SCw.Botao__padrao___bm8eC.Botao__pequeno___UA6ZN.Dropdown__botaoComolink___X0JBb"))
                )
                filtro_dropdown.click()
                
                # Selecionar "todos os produtos"
                todos_produtos = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//li[text()='todos os produtos']"))
                )
                todos_produtos.click()
                time.sleep(3)  # Aguardar atualização da tabela
                logger.info("Filtro 'todos os produtos' aplicado com sucesso!")
            except Exception as e:
                logger.warning(f"⚠️ Erro ao aplicar filtro 'todos os produtos': {e}")
                # Continuar mesmo se o filtro falhar, pois pode já estar selecionado

            return True

        except TimeoutException:
            logger.warning("Tentando navegação via menu...")
            try:
                WebDriverWait(driver, 15).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/produtos')]"))
                ).click()
                
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#listagem_produto"))
                )
                logger.info("Navegação via menu concluída!")
                return True
            except:
                logger.error("Falha na navegação")
                return False

    def _extrair_dados_produtos(self, driver):
        """Extrai dados dos produtos da tabela"""
        produtos = []
        
        while True:
            logger.info("Extraindo dados da página atual...")
            
            tabela = driver.find_element(By.ID, "listagem_produto")
            linhas = tabela.find_elements(By.TAG_NAME, "tr")[1:]
            
            for linha in linhas:
                colunas = linha.find_elements(By.TAG_NAME, "td")
                if len(colunas) >= 9:
                    estoque_valor = colunas[6].text.strip().split()[0].replace('.', '')
                    produtos.append({
                        "SKU": colunas[2].text.strip(),
                        "Produto": colunas[3].text.strip(),
                        "Depósito": "Grupo Vision",
                        "Estoque": int(estoque_valor) if estoque_valor.isdigit() else None
                    })
            
            try:
                WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[text()='Próxima']"))
                ).click()
                time.sleep(2)
            except:
                break
                
        logger.info(f"Extraídos {len(produtos)} produtos no total")
        return produtos

    def carrega_dados_mercos(self) -> pd.DataFrame:
        """Método principal para carregar dados do Mercos"""
        start_time = time.time()
        load_dotenv()

        try:
            # Inicializar o ChromeDriver usando webdriver-manager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=self.chrome_options)
            logger.info("WebDriver inicializado com sucesso")

            if not self._login(driver):
                return pd.DataFrame()

            if not self._navegar_para_produtos(driver):
                return pd.DataFrame()

            produtos = self._extrair_dados_produtos(driver)
            
            if produtos:
                df = pd.DataFrame(produtos)
                self.df_filtrado = df[df['Estoque'] > 0]
                logger.info(f"Dados extraídos com sucesso! Total: {len(produtos)} produtos")
                
                # Salvar dados no banco de dados
                try:
                    db = DatabaseManager()
                    db.salvar_estoque_mercos(self.df_filtrado)
                    logger.info("Dados salvos no banco de dados com sucesso")
                except Exception as e:
                    logger.error(f"Erro ao salvar dados no banco: {e}")
            else:
                self.df_filtrado = pd.DataFrame()
                logger.warning("Nenhum produto encontrado")

        except Exception as e:
            logger.error(f"Erro durante a execução: {e}")
            self.df_filtrado = pd.DataFrame()

        finally:
            driver.quit()
            tempo_total = time.time() - start_time
            logger.info(f"Tempo total do processo: {tempo_total:.2f} segundos")

        return self.df_filtrado

if __name__ == "__main__":
    try:
        mercos_rasp = MercosWebScraping()
        df = mercos_rasp.carrega_dados_mercos()
        
        if not df.empty:
            print("\nRelatório de Estoque Mercos - Estoque Próprio")
            print("=" * 60)
            print(df.to_string(index=False))
        else:
            print("Nenhum dado encontrado.")
            
    except Exception as e:
        print(f"Erro na execução: {str(e)}")