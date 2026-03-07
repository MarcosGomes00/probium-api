import json
import random
from services.bet_resolver import resolver_aposta

HISTORY_FILE = "bets_history.json"


def check_results():

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            bets = json.load(f)
    except Exception as e:
        print("⚠️ Erro ao abrir histórico:", e)
        bets = []

    updated = False

    for bet in bets:

        # se já foi verificado pula
        if bet.get("checked"):
            continue

        market = bet.get("market")
        home_score = bet.get("home_score")
        away_score = bet.get("away_score")

        # se ainda não temos placar usamos simulação
        if home_score is None or away_score is None:

            outcome = random.choice(["GREEN", "RED"])

        else:

            outcome = resolver_aposta(
                market,
                home_score,
                away_score
            )

        bet["result"] = outcome
        bet["checked"] = True

        updated = True

    if updated:

        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(bets, f, indent=2)

        print("✅ Resultados atualizados no histórico")

    else:

        print("ℹ️ Nenhuma aposta nova para verificar")