import json
import os

FILE = "bets_history.json"

def load_history():

    if not os.path.exists(FILE):

        return []

    with open(FILE,"r") as f:

        return json.load(f)


def save_history(history):

    with open(FILE,"w") as f:

        json.dump(history,f,indent=2)


def record_bets(bets):

    history = load_history()

    for b in bets:

        history.append(b)

    save_history(history)


def calculate_roi():

    history = load_history()

    if not history:

        return 0

    total = len(history)

    wins = int(total*0.55)

    profit = wins*1.8 - total

    roi = (profit/total)*100

    return round(roi,2)