from sqlmodel import SQLModel, Session, create_engine
from dotenv import load_dotenv
import os
from urllib.parse import urlparse
from sqlalchemy import text
from sqlalchemy.orm import sessionmaker
import logging
import pandas as pd
from datetime import datetime
from .models import EstoqueMercos, ConciliacaoMercos
from sqlalchemy.sql import delete, select

logger = logging.getLogger(__name__)

# Carrega variáveis do .env
load_dotenv()

def get_database_url():
    """Configura e retorna a URL do banco de dados"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("A variável DATABASE_URL não foi encontrada no arquivo .env")
    
    # Ajuste para o Neon
    parsed_url = urlparse(database_url)
    if parsed_url.scheme == "postgres":
        database_url = database_url.replace("postgres://", "postgresql://")
    
    return database_url

def create_database_engine():
    """Cria e retorna o engine do banco de dados com configurações apropriadas"""
    database_url = get_database_url()
    ssl_mode = 'require'  # Ou 'verify-full' dependendo da sua necessidade
    return create_engine(database_url, echo=True, connect_args={'sslmode': ssl_mode})

# Engine global
engine = create_database_engine()

def init_db():
    """Cria todas as tabelas no banco de dados"""
    SQLModel.metadata.create_all(engine)

def get_session():
    """
    Retorna uma nova sessão de banco de dados.
    Use um bloco 'with' para garantir que a sessão seja fechada automaticamente.
    """
    return Session(engine)

class DatabaseManager:
    def __init__(self):
        self.engine = engine  # Usa o engine global
        self.Session = sessionmaker(bind=self.engine)
        self._create_tables()

    def _create_tables(self):
        """Cria as tabelas necessárias se não existirem"""
        # Cria todas as tabelas definidas nos modelos
        SQLModel.metadata.create_all(self.engine)
        logger.info("Todas as tabelas foram criadas/atualizadas com sucesso")

    def salvar_estoque_mercos(self, df: pd.DataFrame) -> None:
        """Salva os dados de estoque do Mercos no banco de dados"""
        try:
            with Session(self.engine) as session:
                # Primeiro, limpa a tabela existente
                session.exec(delete(EstoqueMercos))
                
                # Insere os novos dados
                for _, row in df.iterrows():
                    estoque = EstoqueMercos(
                        sku=row['SKU'],
                        produto=row['Produto'],
                        deposito=row['Depósito'],
                        quantidade=row['Estoque']
                    )
                    session.add(estoque)
                
                # Commit da transação
                session.commit()
                logger.info("Dados de estoque do Mercos atualizados com sucesso")
                
        except Exception as e:
            logger.error(f"Erro ao salvar dados de estoque do Mercos: {e}")
            raise

    def obter_estoque_mercos(self):
        """Recupera os dados de estoque do Mercos"""
        try:
            with Session(self.engine) as session:
                # Usa select() do SQLModel para buscar todos os registros
                statement = select(EstoqueMercos)
                results = session.exec(statement).all()
                return results
        except Exception as e:
            logger.error(f"Erro ao recuperar dados do banco: {e}")
            return []