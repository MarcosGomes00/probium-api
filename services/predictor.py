import random

def predict_match(home_team, away_team):

    home_win = round(random.uniform(0.40, 0.60), 2)
    draw = round(random.uniform(0.20, 0.30), 2)
    away_win = round(1 - home_win - draw, 2)

    expected_goals_home = round(random.uniform(1.2, 2.0), 2)
    expected_goals_away = round(random.uniform(0.8, 1.6), 2)

    return {
        "home_team": home_team,
        "away_team": away_team,
        "probabilities": {
            "home_win": home_win,
            "draw": draw,
            "away_win": away_win
        },
        "expected_goals": {
            "home": expected_goals_home,
            "away": expected_goals_away
        }
    }