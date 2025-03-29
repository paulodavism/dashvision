# app_dv_smartshop/src/config.py
import os
from dotenv import load_dotenv

def load_settings():
    """Carrega configurações do ambiente"""
    env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(env_path)
    
    required_vars = [
        'MERCADO_LIVRE_CLIENT_ID',
        'MERCADO_LIVRE_CLIENT_SECRET',
        'MERCADO_LIVRE_USER_ID'
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise EnvironmentError(
            f"Variáveis de ambiente faltando: {', '.join(missing)}"
        )