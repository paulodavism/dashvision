import time
import os
import logging
import urllib.parse
from typing import Dict, List, Optional
import pandas as pd
import requests
from dotenv import load_dotenv
from requests.exceptions import HTTPError, RequestException

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

class AmazonAPIError(Exception):
    """Exceção personalizada para erros da API da Amazon"""
    pass

class AmazonTokenManager:
    """Gerencia a autenticação e renovação de tokens da Amazon SP-API"""
    
    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token_value = refresh_token  # Atributo renomeado
        self.access_token: Optional[str] = None

    def renew_token(self) -> None:  # Método renomeado
        """Renova o token de acesso usando refresh token"""
        url = "https://api.amazon.com/auth/o2/token"
        payload = {
            "grant_type": "refresh_token",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token_value
        }
        
        try:
            response = requests.post(
                url,
                data=urllib.parse.urlencode(payload),
                headers={'Content-Type': 'application/x-www-form-urlencoded'},
                timeout=15
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            logger.info("Token da Amazon renovado com sucesso")
            
        except HTTPError as e:
            logger.error(f"Erro ao renovar token: {e.response.text}")
            raise AmazonAPIError("Falha na renovação do token") from e

class AmazonAPI:
    """Classe principal para integração com a API de estoque da Amazon"""
    
    def __init__(self):
        self.client_id = os.getenv("AMAZON_CLIENT_ID")
        self.client_secret = os.getenv("AMAZON_CLIENT_SECRET")
        refresh_token = os.getenv("AMAZON_REFRESH_TOKEN")
        self.marketplace_id = os.getenv("AMAZON_MARKETPLACE_ID", "A2Q3Y263D00KWC")
        self.endpoint = os.getenv("AMAZON_ENDPOINT", "https://sellingpartnerapi-na.amazon.com")
        
        self.token_manager = AmazonTokenManager(
            self.client_id,
            self.client_secret,
            refresh_token
        )
        
        self._validate_credentials()
        self._setup_session()

    def _validate_credentials(self) -> None:
        """Valida as credenciais essenciais"""
        missing = []
        if not self.client_id:
            missing.append("AMAZON_CLIENT_ID")
        if not self.client_secret:
            missing.append("AMAZON_CLIENT_SECRET")
        if not self.token_manager.refresh_token_value:
            missing.append("AMAZON_REFRESH_TOKEN")
            
        if missing:
            raise AmazonAPIError(
                f"Credenciais faltando no .env: {', '.join(missing)}"
            )

    def _setup_session(self) -> None:
        """Configura sessão HTTP reutilizável"""
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DVSmartShop/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

    def _make_request(self, path: str, params: Optional[Dict] = None) -> Dict:
        """Executa requisições à API com tratamento de erros"""
        url = f"{self.endpoint}{path}"
        params = params or {}
        
        try:
            if not self.token_manager.access_token:
                self.token_manager.renew_token()
                
            self.session.headers.update({
                "x-amz-access-token": self.token_manager.access_token
            })
            
            response = self.session.get(url, params=params, timeout=15)
            logger.debug(f"Resposta bruta da API: {response.text}")  # Para debug
            response.raise_for_status()
            
            self._check_rate_limits(response.headers)
            
            return response.json()
            
        except HTTPError as e:
            if e.response.status_code in (401, 403):
                logger.warning("Token expirado, tentando renovar...")
                self.token_manager.renew_token()
                return self._make_request(path, params)
            logger.error(f"Erro na API: {e.response.text}")
            raise AmazonAPIError("Erro na requisição à API") from e
            
        except RequestException as e:
            logger.error(f"Erro de conexão: {str(e)}")
            raise AmazonAPIError("Erro de conexão") from e

    def _check_rate_limits(self, headers: Dict) -> None:
        """Verifica e respeita os rate limits da API"""
        # Corrigir a conversão para lidar com valores decimais como strings
        rate_limit = headers.get("x-amzn-RateLimit-Limit", "15")  # Valor padrão como string
        remaining = int(float(rate_limit))  # Converter para float primeiro
        
        if remaining < 5:
            reset_time = int(headers.get("x-amzn-RateLimit-Reset", "2"))  # Garantir conversão segura aqui também
            logger.warning(f"Rate limit atingido. Aguardando {reset_time}s")
            time.sleep(reset_time + 1)        

    def gerar_relatorio_estoque(self) -> pd.DataFrame:
        """Obtém resumo completo do estoque FBA"""
        try:
            logger.info("Obtendo resumo de estoque da Amazon...")
            data = self._make_request(
                "/fba/inventory/v1/summaries",
                params={
                    "granularityType": "Marketplace",
                    "granularityId": self.marketplace_id,
                    "marketplaceIds": self.marketplace_id,
                    "details": "true"
                }
            )
            
            inventory_data = data.get("payload", {}).get("inventorySummaries", [])
            return self._parse_inventory_data(inventory_data)
            
        except AmazonAPIError as e:
            logger.error(f"Falha ao obter estoque: {str(e)}")
            return pd.DataFrame()

    def _parse_inventory_data(self, raw_data: List[Dict]) -> pd.DataFrame:
        """Processa dados brutos da API para DataFrame estruturado usando pandas"""
        try:
            # Cria DataFrame normalizado
            df = pd.json_normalize(raw_data)
            
            # Renomeia colunas
            df = df.rename(columns={
                "sellerSku": "SKU",
                "productName": "Nome",
                "inventoryDetails.fulfillableQuantity": "Estoque"
            })
            
            # Seleciona e ordena colunas
            df = df[["SKU", "Nome", "Estoque"]]
            
            # Conversão segura de tipos numéricos
            numeric_cols = ["Estoque"]
            df[numeric_cols] = df[numeric_cols].apply(
                pd.to_numeric, errors='coerce'
            ).fillna(0).astype(int)
            
            # Formata strings
            df["Nome"] = df["Nome"].str[:70].fillna("")
            
            return df
            
        except Exception as e:
            logger.error(f"Erro no processamento dos dados: {str(e)}")
            return pd.DataFrame()

if __name__ == "__main__":
    try:
        amazon_api = AmazonAPI()
        df = amazon_api.gerar_relatorio_estoque()
        
        if not df.empty:
            print("\nRelatório de Estoque Amazon FBA")
            print("=" * 60)
            print(df.to_string(index=False))
        else:
            print("Nenhum dado encontrado.")
            
    except AmazonAPIError as e:
        print(f"Erro na execução: {str(e)}")