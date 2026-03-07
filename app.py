from flask import Flask, request, jsonify
from sqlalchemy import text
from threading import Thread

from config import Config
from services.database import db

from routes.predict import predict_bp
from routes.stats import stats_bp

from services.scheduler import start_scheduler
from services.telegram_bot import init_bot
from services.history_collector import collect_top_leagues


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)


# =========================
# CRIAR TABELA AUTOMATICAMENTE
# =========================

with app.app_context():

    db.engine.execute(text("""

    CREATE TABLE IF NOT EXISTS matches_history (

        id INTEGER PRIMARY KEY AUTOINCREMENT,

        league TEXT,
        season TEXT,
        date TEXT,

        home_team TEXT,
        away_team TEXT,

        home_goals INTEGER,
        away_goals INTEGER

    )

    """))


# =========================
# ROTAS PRINCIPAIS
# =========================

app.register_blueprint(predict_bp)
app.register_blueprint(stats_bp)


@app.route("/")
def home():
    return {
        "status": "PROBIUM API ONLINE"
    }


# =========================
# IMPORTAR HISTÓRICO
# =========================

@app.route("/import-history")
def import_history():

    def run_import():
        try:
            collect_top_leagues()
            print("History import finished")
        except Exception as e:
            print("History import error:", e)

    Thread(target=run_import).start()

    return {
        "status": "started",
        "message": "history import running in background"
    }


# =========================
# INICIALIZAÇÕES
# =========================

init_bot()

start_scheduler(app)