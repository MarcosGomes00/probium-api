from services.poisson_model import match_prediction


# força ofensiva estimada dos times
TEAM_STRENGTH = {

    "Flamengo": 1.8,
    "Palmeiras": 1.6,
    "Barcelona": 2.0,
    "Real Madrid": 2.1,
    "Liverpool": 2.0,
    "Man City": 2.2,
    "PSG": 2.0,
    "Bayern": 2.1

}


def predict_match(home, away):

    # se time não existir usa média
    home_attack = TEAM_STRENGTH.get(home, 1.5)
    away_attack = TEAM_STRENGTH.get(away, 1.5)

    result = match_prediction(home_attack, away_attack)

    return {
        "home": home,
        "away": away,
        "prob_home_win": result["home_win"],
        "prob_draw": result["draw"],
        "prob_away_win": result["away_win"]
    }