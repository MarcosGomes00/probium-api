from services.match_scanner import get_today_matches
from services.predictor import predict_match


def analyze_today_matches():

    matches = get_today_matches()

    results = []

    for match in matches:

        prediction = predict_match(
            match["home"],
            match["away"]
        )

        results.append(prediction)

    return results