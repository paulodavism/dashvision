import psycopg2
import os
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

def create_users_table():
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) UNIQUE NOT NULL,
            name VARCHAR(100) NOT NULL,
            password_hash VARCHAR(255) NOT NULL
        );
    ''')
    conn.commit()
    cur.close()
    conn.close()
    print('Tabela users criada com sucesso.')

if __name__ == "__main__":
    create_users_table()
