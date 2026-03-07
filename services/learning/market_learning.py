import json

# ===============================
# ANALISAR HISTÓRICO DE APOSTAS
# ===============================

def analyze_markets():

    try:

        with open("bets_history.json") as f:
            bets = json.load(f)

    except:

        print("Nenhum histórico encontrado")
        return


    markets = {}

    for bet in bets:

        market = bet.get("market")
        status = bet.get("status")

        if not market:
            continue

        if market not in markets:

            markets[market] = {
                "wins": 0,
                "losses": 0
            }

        if status == "TAKE":
            markets[market]["wins"] += 1

        elif status == "RED":
            markets[market]["losses"] += 1


    print("\n📊 MARKET PERFORMANCE\n")

    weights = {}

    for m, data in markets.items():

        total = data["wins"] + data["losses"]

        if total == 0:
            continue

        winrate = round((data["wins"] / total) * 100, 2)

        print(f"{m}")
        print(f"Take: {data['wins']}")
        print(f"Red: {data['losses']}")
        print(f"Winrate: {winrate}%\n")

        weights[m] = winrate / 100


    # salvar pesos aprendidos
    with open("market_weights.json", "w") as f:

        json.dump(weights, f, indent=2)

    print("🧠 Pesos de mercado atualizados")


if __name__ == "__main__":

    analyze_markets()