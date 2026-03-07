import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# ==============================================================
# 1. CRIA O APP E O BANCO PRIMEIRO (Isso resolve o erro da Linha 2)
# ==============================================================
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///probum.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ==============================================================
# 2. CRIA A TABELA DO JEITO NOVO (Pra não dar erro no Gunicorn)
# ==============================================================
with app.app_context():
    with db.engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS operacoes_tipster (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fixture_id INTEGER,
            jogo TEXT,
            data_hora TEXT,
            mercado_tipo TEXT,  -- Ex: "HOME", "OVER25", "BTTS"
            odd REAL,
            status TEXT DEFAULT 'PENDENTE', -- Muda pra 'GREEN' ou 'RED' depois
            id_mensagem_telegram INTEGER
        )
        """))

# ==============================================================
# DAQUI PARA BAIXO VOCÊ DEIXA O RESTO DO SEU CÓDIGO DO JEITO QUE TÁ!
# (Não apague as suas funções do Telegram, The Odds API, etc)
# ==============================================================