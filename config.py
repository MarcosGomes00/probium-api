
import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY","probum-secret")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///probum.db"
    )

    BOT1_TOKEN = os.getenv("BOT1_TOKEN")
    BOT2_TOKEN = os.getenv("BOT2_TOKEN")

    TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")

    TIMEZONE = "America/Sao_Paulo"
import os

class Config:

    SECRET_KEY = os.getenv("SECRET_KEY", "probum-secret")

    DATABASE_URL = os.getenv("DATABASE_URL")

    if DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = DATABASE_URL
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///probum.db"

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    BOT1_TOKEN = os.getenv("BOT1_TOKEN")
    BOT2_TOKEN = os.getenv("BOT2_TOKEN")

    TELEGRAM_GROUP_ID = os.getenv("TELEGRAM_GROUP_ID")

    TIMEZONE = os.getenv("TIMEZONE", "America/Sao_Paulo")