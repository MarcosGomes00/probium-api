from services.poisson_model import calculate_goal_matrix, calculate_match_probabilities
import random


def predict_match(home_team, away_team):

    # valores fictícios de força ofensiva (temporário)
    home_xg = round(random.uniform(1.2, 2.0), 2)
    away_xg = round(random.uniform(0.8, 1.6), 2)

    matrix = calculate_goal_matrix(home_xg, away_xg)

    home_win, draw, away_win = calculate_match_probabilities(matrix)

    return {
        "home_team": home_team,
        "away_team": away_team,
        "expected_goals": {
            "home": round(home_xg, 2),
            "away": round(away_xg, 2)
        },
        "probabilities": {
            "home_win": round(home_win, 3),
            "draw": round(draw, 3),
            "away_win": round(away_win, 3)
        }
    }