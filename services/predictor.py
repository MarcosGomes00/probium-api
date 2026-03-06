from services.poisson_model import match_prediction


def bar(prob):

    blocks = int(prob * 10)

    return "█" * blocks + "░" * (10 - blocks)


def predict_match(home, away):

    result = match_prediction(home, away)

    return {

        "probabilities": {

            "home_win": {
                "prob": result["home_win"],
                "bar": bar(result["home_win"])
            },

            "draw": {
                "prob": result["draw"],
                "bar": bar(result["draw"])
            },

            "away_win": {
                "prob": result["away_win"],
                "bar": bar(result["away_win"])
            }

        }

    }