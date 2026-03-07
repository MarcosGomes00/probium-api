import requests
from flask import Flask
from sqlalchemy import text

from config import Config
from services.database import db


def check_database():

    print("🔎 Verificando banco de dados...")

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    with app.app_context():

        try:
            result = db.session.execute(
                text("SELECT COUNT(*) FROM matches_history")
            ).fetchone()

            print("✅ Banco conectado")
            print("📊 Jogos no banco:", result[0])

        except Exception as e:
            print("❌ Erro no banco:", e)


def check_api_football():

    print("\n🔎 Verificando API Football...")

    url = "https://v3.football.api-sports.io/status"

    headers = {
        "x-apisports-key": Config.API_FOOTBALL_KEY
    }

    try:

        r = requests.get(url, headers=headers, timeout=10)

        if r.status_code == 200:
            print("✅ API Football funcionando")
        else:
            print("❌ API Football erro:", r.status_code)

    except Exception as e:
        print("❌ API Football falhou:", e)


def check_odds_api():

    print("\n🔎 Verificando Odds API...")

    url = f"https://api.the-odds-api.com/v4/sports/?apiKey={Config.ODDS_API_KEY}"

    try:

        r = requests.get(url, timeout=10)

        if r.status_code == 200:
            print("✅ Odds API funcionando")
        else:
            print("❌ Odds API erro:", r.status_code)

    except Exception as e:
        print("❌ Odds API falhou:", e)


def check_telegram():

    print("\n🔎 Verificando Telegram Bot...")

    token = Config.TELEGRAM_BOT_TOKEN_1

    url = f"https://api.telegram.org/bot{token}/getMe"

    try:

        r = requests.get(url)

        data = r.json()

        if data["ok"]:
            print("✅ Telegram bot conectado")
            print("🤖 Bot:", data["result"]["username"])
        else:
            print("❌ Telegram bot falhou")

    except Exception as e:
        print("❌ Telegram erro:", e)


def run_system_check():

    print("\n🚀 INICIANDO DIAGNÓSTICO DO SISTEMA\n")

    check_database()
    check_api_football()
    check_odds_api()
    check_telegram()

    print("\n🏁 Diagnóstico finalizado\n")


if __name__ == "__main__":
    run_system_check()