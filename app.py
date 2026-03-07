from flask import Flask
from config import Config
from services.database import db

from routes.predict import predict_bp
from routes.stats import stats_bp

from services.scheduler import start_scheduler
from services.telegram_bot import init_bot


app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

# registrar rotas
app.register_blueprint(predict_bp)
app.register_blueprint(stats_bp)

# iniciar bot telegram
init_bot()

# iniciar scheduler
start_scheduler()


@app.route("/")
def home():
    return {"status": "PROBIUM AI running"}