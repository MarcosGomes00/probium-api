from services.poisson_model import calculate_goal_matrix, calculate_match_probabilities
import random

def probability_bar(value):
    filled = int(value * 10)
    empty = 10 - filled
    return "█" * filled + "░" * empty

def predict_match(home_team, away_team):

    home_xg = round(random.uniform(1.4, 2.0), 2)
    away_xg = round(random.uniform(0.9, 1.6), 2)

    matrix = calculate_goal_matrix(home_xg, away_xg)

    home_win, draw, away_win = calculate_match_probabilities(matrix)

    result = {

        "match": f"{home_team} vs {away_team}",

        "expected_goals": {
            "home": home_xg,
            "away": away_xg
        },

        "probabilities": {

            "home_win": {
                "prob": round(home_win,3),
                "bar": probability_bar(home_win)
            },

            "draw": {
                "prob": round(draw,3),
                "bar": probability_bar(draw)
            },

            "away_win": {
                "prob": round(away_win,3),
                "bar": probability_bar(away_win)
            }

        }

    }

    return result