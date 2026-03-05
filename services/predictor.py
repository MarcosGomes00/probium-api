import random

def predict_match(home_team, away_team):

    home_win = round(random.uniform(0.35, 0.60), 2)
    draw = round(random.uniform(0.20, 0.30), 2)
    away_win = round(1 - home_win - draw, 2)

    return {
        "home_team": home_team,
        "away_team": away_team,
        "probabilities": {
            "home_win": home_win,
            "draw": draw,
            "away_win": away_win
        }
    }