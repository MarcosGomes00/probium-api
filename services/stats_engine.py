import json
import os

HISTORY_FILE = "bets_history.json"


def load_history():

    if not os.path.exists(HISTORY_FILE):
        return []

    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []


def calculate_stats():

    history = load_history()

    if not history:
        return {
            "total_bets": 0,
            "elite": 0,
            "forte": 0,
            "boa": 0,
            "avg_prob": 0,
            "avg_ev": 0
        }

    total = len(history)

    elite = 0
    forte = 0
    boa = 0

    prob_sum = 0
    ev_sum = 0

    for bet in history:

        prob_sum += bet.get("prob", 0)
        ev_sum += bet.get("ev", 0)

        confidence = bet.get("confidence", "")

        if "ELITE" in confidence:
            elite += 1
        elif "FORTE" in confidence:
            forte += 1
        elif "BOA" in confidence:
            boa += 1

    return {
        "total_bets": total,
        "elite": elite,
        "forte": forte,
        "boa": boa,
        "avg_prob": round(prob_sum / total, 4),
        "avg_ev": round(ev_sum / total, 4)
    }