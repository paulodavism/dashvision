import streamlit as st
import psycopg2
import os
from dotenv import load_dotenv
from src.utils.auth_utils import verify_password
import importlib

# Carrega variáveis do .env
load_dotenv()

# Função para buscar usuário no banco
def get_user(username):
    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()
    cur.execute('SELECT username, name, password_hash FROM users WHERE username = %s', (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user

def login_screen():
    st.title('Login - DashVision')
    username = st.text_input('Usuário')
    password = st.text_input('Senha', type='password')
    login_btn = st.button('Entrar')
    if login_btn:
        user = get_user(username)
        if user and verify_password(password, user[2]):
            st.session_state['authenticated'] = True
            st.session_state['username'] = user[0]
            st.session_state['name'] = user[1]
            st.success(f'Bem-vindo, {user[1]}!')
            st.rerun()
        else:
            st.error('Usuário ou senha inválidos.')

def main():
    if 'authenticated' not in st.session_state or not st.session_state['authenticated']:
        st.set_page_config(page_title="Login - DashVision", layout="centered")
        login_screen()
    else:
        # Importa e executa o dashboard real após autenticação
        main_module = importlib.import_module('src.main')
        if hasattr(main_module, 'main'):
            main_module.main()
        else:
            st.error('Função main() não encontrada em src/main.py')

if __name__ == "__main__":
    main()
