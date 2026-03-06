import os
from dotenv import load_dotenv

# carregar variáveis do .env
load_dotenv()

class Config:

    SECRET_KEY = os.getenv("SECRET_KEY", "probium-secret")

    DATABASE_URL = os.getenv("DATABASE_URL")

    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///probium.db"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BOT1_TOKEN = os.getenv("BOT1_TOKEN")
    BOT2_TOKEN = os.getenv("BOT2_TOKEN")

    TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")

    API_KEY = os.getenv("API_KEY")

    ADMIN_USER = os.getenv("ADMIN_USER")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

    TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")