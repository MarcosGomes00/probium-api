import json
import requests


FILE_PATH = "bets_history.json"


def load_bets():

    try:

        with open(FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    except:
        return []


def save_bets(data):

    with open(FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def check_results():

    bets = load_bets()

    updated = False

    for bet in bets:

        if bet.get("status") != "pending":
            continue

        home = bet["home"]
        away = bet["away"]

        try:

            # API de resultados (exemplo simples)
            url = f"https://api.sampleapis.com/futurama/episodes"

            response = requests.get(url)

            if response.status_code != 200:
                continue

            # simulação de resultado
            home_goals = 2
            away_goals = 1

            bet_type = bet["market"]

            if bet_type == "home_win" and home_goals > away_goals:
                bet["status"] = "green"

            elif bet_type == "away_win" and away_goals > home_goals:
                bet["status"] = "green"

            elif bet_type == "draw" and home_goals == away_goals:
                bet["status"] = "green"

            else:
                bet["status"] = "red"

            updated = True

        except:
            continue

    if updated:
        save_bets(bets)