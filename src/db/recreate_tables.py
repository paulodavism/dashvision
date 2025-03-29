from src.db.database import DatabaseManager
import logging
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def recreate_tables():
    """Recria todas as tabelas do banco de dados"""
    try:
        # Inicializa o gerenciador do banco de dados
        db = DatabaseManager()
        
        # Conecta ao banco de dados
        with db.engine.connect() as conn:
            # Dropa as tabelas existentes
            conn.execute(text("DROP TABLE IF EXISTS estoque_mercos CASCADE"))
            conn.execute(text("DROP TABLE IF EXISTS conciliacao_mercos CASCADE"))
            conn.commit()
            
            # Cria as tabelas novamente
            db._create_tables()
            
            logger.info("✅ Tabelas recriadas com sucesso!")
            
    except Exception as e:
        logger.error(f"❌ Erro ao recriar tabelas: {e}")
        raise

if __name__ == "__main__":
    recreate_tables() 