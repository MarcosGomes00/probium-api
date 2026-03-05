from services.match_scanner import get_today_matches
from services.predictor import predict_match
from services.value_bet import find_value_bet


def analyze_today_matches():

    matches = get_today_matches()

    results = []

    for match in matches:

        prediction = predict_match(
            match["home"],
            match["away"]
        )

        value = find_value_bet(

            prediction["probabilities"]["home_win"]["prob"],
            prediction["probabilities"]["draw"]["prob"],
            prediction["probabilities"]["away_win"]["prob"]

        )

        prediction["value_bet"] = value

        results.append(prediction)

    return results