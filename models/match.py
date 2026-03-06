from services.database import db


class Match(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    home_team = db.Column(db.String(120))
    away_team = db.Column(db.String(120))

    home_goals = db.Column(db.Integer)
    away_goals = db.Column(db.Integer)

    league = db.Column(db.String(120))

    date = db.Column(db.String(50))
