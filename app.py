from flask import Flask
from config import Config
from services.database import db
from sqlalchemy import text

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)


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