import sys
import os

# garante que o projeto raiz seja encontrado
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from flask import Flask
from config import Config
from services.database import db


def create_history_table():

    db.engine.execute(
        """
        CREATE TABLE IF NOT EXISTS matches_history (
            id SERIAL PRIMARY KEY,
            league TEXT,
            season INTEGER,
            date TIMESTAMP,
            home_team TEXT,
            away_team TEXT,
            home_goals INTEGER,
            away_goals INTEGER
        )
        """
    )


if __name__ == "__main__":

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():
        create_history_table()
        print("Tabela matches_history criada com sucesso.")