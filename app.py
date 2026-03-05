from flask import Flask
from config import Config
from services.database import db
from services.telegram_bot import init_telegram
from services.scheduler import start_scheduler
from routes.predict import predict_bp


def create_app():

    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    # registrar rota predict
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
        start_scheduler()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)