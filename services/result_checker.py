import json
import random


HISTORY_FILE = "bets_history.json"


def check_results():

    try:
        with open(HISTORY_FILE, "r") as f:
            bets = json.load(f)
    except:
        bets = []

    updated = False

    for bet in bets:

        # se já foi verificado pula
        if bet.get("checked"):
            continue

        # simulação de resultado (depois vamos usar API real)
        outcome = random.choice(["GREEN", "RED"])

        bet["result"] = outcome
        bet["checked"] = True

        updated = True

    if updated:
        with open(HISTORY_FILE, "w") as f:
            json.dump(bets, f, indent=2)

        print("✅ Resultados atualizados no histórico")

    else:
        print("ℹ️ Nenhuma aposta nova para verificar")