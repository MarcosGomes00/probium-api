from services.poisson_model import calculate_goal_matrix, calculate_match_probabilities
import random


def calculate_over_under(matrix):

    over = 0
    under = 0

    for home_goals in range(len(matrix)):
        for away_goals in range(len(matrix)):

            total_goals = home_goals + away_goals

            if total_goals > 2:
                over += matrix[home_goals][away_goals]
            else:
                under += matrix[home_goals][away_goals]

    return over, under


def predict_match(home_team, away_team):

    # valores temporários de xG
    home_xg = round(random.uniform(1.2, 2.0), 2)
    away_xg = round(random.uniform(0.8, 1.6), 2)

    matrix = calculate_goal_matrix(home_xg, away_xg)

    home_win, draw, away_win = calculate_match_probabilities(matrix)

    over25, under25 = calculate_over_under(matrix)

    result = {
        "home_team": home_team,
        "away_team": away_team,
        "expected_goals": {
            "home": home_xg,
            "away": away_xg
        },
        "probabilities": {
            "home_win": round(home_win, 3),
            "draw": round(draw, 3),
            "away_win": round(away_win, 3)
        },
        "over_under_2_5": {
            "over": round(over25, 3),
            "under": round(under25, 3)
        }
    }

    return result