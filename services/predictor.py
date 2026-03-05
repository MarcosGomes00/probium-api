from services.poisson_model import calculate_goal_matrix, calculate_match_probabilities
import random


def probability_bar(value):

    filled = int(value * 10)
    empty = 10 - filled

    return "█" * filled + "░" * empty


def signal_strength(value):

    if value >= 0.65:
        return "🔥 Forte"

    elif value >= 0.50:
        return "⚡ Médio"

    else:
        return "⚠️ Fraco"


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


def calculate_btts(matrix):

    yes = 0
    no = 0

    for home_goals in range(len(matrix)):
        for away_goals in range(len(matrix)):

            prob = matrix[home_goals][away_goals]

            if home_goals > 0 and away_goals > 0:
                yes += prob
            else:
                no += prob

    return yes, no


def get_top_scores(matrix):

    scores = []

    for home_goals in range(len(matrix)):
        for away_goals in range(len(matrix)):

            prob = matrix[home_goals][away_goals]

            scores.append({
                "score": f"{home_goals}-{away_goals}",
                "prob": prob
            })

    scores_sorted = sorted(scores, key=lambda x: x["prob"], reverse=True)

    return scores_sorted[:3]


def predict_match(home_team, away_team):

    home_xg = round(random.uniform(1.2, 2.0), 2)
    away_xg = round(random.uniform(0.8, 1.6), 2)

    matrix = calculate_goal_matrix(home_xg, away_xg)

    home_win, draw, away_win = calculate_match_probabilities(matrix)

    over25, under25 = calculate_over_under(matrix)

    btts_yes, btts_no = calculate_btts(matrix)

    top_scores = get_top_scores(matrix)

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

        "signals": {

            "home_win": {
                "prob": round(home_win, 3),
                "bar": probability_bar(home_win),
                "strength": signal_strength(home_win),
                "emoji": "🏠"
            },

            "draw": {
                "prob": round(draw, 3),
                "bar": probability_bar(draw),
                "strength": signal_strength(draw),
                "emoji": "🤝"
            },

            "away_win": {
                "prob": round(away_win, 3),
                "bar": probability_bar(away_win),
                "strength": signal_strength(away_win),
                "emoji": "✈️"
            }

        },

        "over_under_2_5": {
            "over": round(over25, 3),
            "under": round(under25, 3)
        },

        "btts": {
            "yes": round(btts_yes, 3),
            "no": round(btts_no, 3)
        },

        "top_scores": [
            {"score": s["score"], "prob": round(s["prob"], 3)}
            for s in top_scores
        ]
    }

    return result