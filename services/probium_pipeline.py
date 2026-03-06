from datetime import datetime
import random

from services.data_source import get_matches_today
from services.poisson_model import over25_prob, btts_prob
from services.telegram_bot import send_bet_message


MIN_PROB = 0.57


def format_message(bets):

    header = f"""
🤖 **PROBIUM AI SCANNER**

📅 {datetime.now().strftime("%d/%m/%Y")}
⚽ Top análises do dia

━━━━━━━━━━━━━━━━━━
"""

    body = ""

    for b in bets:

        prob = round(b["prob"] * 100, 1)

        bar = "🟩" * int(prob / 10)

        body += f"""
🏆 **{b['league']}**

⚽ {b['home']} vs {b['away']}

🎯 **Entrada:** {b['market']}

📊 **Probabilidade:** {prob}%
{bar}

━━━━━━━━━━━━━━━━━━
"""

    footer = """
📈 Modelo Probium AI
⚠️ Gestão de banca recomendada
"""

    return header + body + footer


def run_pipeline():

    print("🔎 PROBIUM analisando jogos...")

    matches = get_matches_today()

    print(f"⚽ {len(matches)} jogos encontrados")

    bets = []

    for m in matches:

        home = m["home"]
        away = m["away"]
        league = m["league"]

        home_attack = random.uniform(1.2, 2.2)
        away_attack = random.uniform(1.0, 2.0)

        over = over25_prob(home_attack, away_attack)
        btts = btts_prob(home_attack, away_attack)
        under = 1 - over

        market = None
        prob = 0

        if over > MIN_PROB:

            market = "OVER 2.5"
            prob = over

        elif btts > MIN_PROB:

            market = "BTTS SIM"
            prob = btts

        elif under > MIN_PROB:

            market = "UNDER 2.5"
            prob = under

        if market:

            bets.append({
                "home": home,
                "away": away,
                "league": league,
                "market": market,
                "prob": prob
            })

    bets = sorted(bets, key=lambda x: x["prob"], reverse=True)

    top = bets[:5]

    if not top:

        print("⚠ Nenhuma aposta encontrada")
        return

    message = format_message(top)

    send_bet_message(message)

    print("📤 Bilhete enviado no Telegram")