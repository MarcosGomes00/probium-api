from services.database import db


class Prediction(db.Model):

    __tablename__ = "predictions"

    id = db.Column(db.Integer, primary_key=True)

    # ⚽ Partida analisada
    match = db.Column(db.String(120))

    # 📊 Expected Goals
    home_xg = db.Column(db.Float)
    away_xg = db.Column(db.Float)

    # 📈 Probabilidades
    home_win = db.Column(db.Float)
    draw = db.Column(db.Float)
    away_win = db.Column(db.Float)

    # 🕒 Data da previsão
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    def to_dict(self):

        return {

            "id": self.id,

            "match": f"⚽ {self.match}",

            "expected_goals": {
                "home": f"🏠 {self.home_xg}",
                "away": f"✈️ {self.away_xg}"
            },

            "probabilities": {

                "home_win": f"🏠 Vitória Casa: {round(self.home_win*100,1)}%",

                "draw": f"🤝 Empate: {round(self.draw*100,1)}%",

                "away_win": f"✈️ Vitória Fora: {round(self.away_win*100,1)}%"
            },

            "created_at": f"🕒 {self.created_at}"
        }