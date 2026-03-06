from dotenv import load_dotenv
import os

load_dotenv()

from models.match import Match
from flask import Flask
from config import Config
from services.database import db
from services.telegram_bot import init_telegram
from services.scheduler import start_scheduler
from routes.predict import predict_bp
from middleware.error_handler import register_error_handlers


def create_app():

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    # registrar middleware
    register_error_handlers(app)

    # registrar rotas
    app.register_blueprint(predict_bp)

    @app.route("/")
    def home():
        return {"status": "probium api online"}

    @app.route("/health")
    def health():
        return {"status": "ok"}

    with app.app_context():
        db.create_all()
        init_telegram(app)
        start_scheduler(app)

    return app


# 🔹 IMPORTANTE: expor app para flask/gunicorn
app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)