import os


class Config:

    # Banco de dados
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///probium.db"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False


    # API Football
    API_FOOTBALL_KEY = "a1b4dc55ed3248a09e8b8582e4dbc0c9"


    # Odds API
    ODDS_API_KEY = "6a1c0078b3ed09b42fbacee8f07e7cc3"


    # Telegram bots
    TELEGRAM_BOT_TOKEN_1 = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
    TELEGRAM_BOT_TOKEN_2 = "8185027087:AAH1JQJKtlWy_oUQpAvqvHEsFIVOK3ScYBc"


    # Canal telegram
    TELEGRAM_CHAT_ID = "-1003814625223"