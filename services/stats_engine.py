import json

FILE_PATH = "bets_history.json"


def load_bets():

    try:

        with open(FILE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    except:

        return []


def calculate_stats():

    bets = load_bets()

    total_bets = len(bets)

    greens = 0
    reds = 0

    profit = 0

    for bet in bets:

        status = bet.get("status")
        odd = bet.get("odd", 1)

        if status == "green":

            greens += 1
            profit += odd - 1

        elif status == "red":

            reds += 1
            profit -= 1

    winrate = 0
    roi = 0

    if total_bets > 0:

        winrate = (greens / total_bets) * 100
        roi = (profit / total_bets) * 100

    return {

        "total_bets": total_bets,
        "greens": greens,
        "reds": reds,
        "winrate": round(winrate, 2),
        "roi": round(roi, 2),
        "profit_units": round(profit, 2)

    }