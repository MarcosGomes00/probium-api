import random

from services.data_source import get_matches_by_date
from services.poisson_model import over25_prob, btts_prob
from services.telegram_bot import send_bet_message


MIN_PROB = 0.57


def run_pipeline():

    print("🔎 PROBIUM analisando partidas...")

    matches = get_matches_by_date("2026-03-07")

    print(f"⚽ {len(matches)} jogos encontrados")

    bets = []

    for m in matches:

        home = m["home"]
        away = m["away"]
        league = m["league"]

        home_attack = random.uniform(1.2, 2.2)
        away_attack = random.uniform(1.0, 2.0)

        over_prob = over25_prob(home_attack, away_attack)
        btts = btts_prob(home_attack, away_attack)
        under_prob = 1 - over_prob

        market = None
        prob = 0

        if over_prob > MIN_PROB:

            market = "OVER 2.5"
            prob = over_prob

        elif btts > MIN_PROB:

            market = "BTTS SIM"
            prob = btts

        elif under_prob > MIN_PROB:

            market = "UNDER 2.5"
            prob = under_prob

        if market:

            bets.append({
                "home": home,
                "away": away,
                "league": league,
                "market": market,
                "prob": prob
            })

    bets = sorted(bets, key=lambda x: x["prob"], reverse=True)

    top = bets[:10]

    if not top:

        print("⚠ Nenhuma análise encontrada")
        return

    for b in top:

        msg = f"""
🤖 PROBIUM AI

🏆 Liga: {b['league']}

⚽ {b['home']} vs {b['away']}

🎯 Entrada: {b['market']}

📊 Probabilidade: {round(b['prob']*100,1)}%
"""

        send_bet_message(msg)

        print("✅ enviada:", b["home"], "vs", b["away"])