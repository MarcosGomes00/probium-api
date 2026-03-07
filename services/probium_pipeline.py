from datetime import datetime, timedelta, timezone
import random

from services.data_source import get_matches_today
from services.poisson_model import over25_prob, btts_prob
from services.telegram_bot import send_bet_message


MIN_PROB = 0.57
MAX_BETS = 5


def run_pipeline():

    print("🔎 PROBIUM analisando jogos...")

    matches = get_matches_today()

    print(f"⚽ {len(matches)} jogos encontrados")

    bets = []

    now = datetime.now(timezone.utc)

    for m in matches:

        home = m.get("home")
        away = m.get("away")
        league = m.get("league")
        kickoff_raw = m.get("time")

        try:
            kickoff_dt = datetime.fromisoformat(
                kickoff_raw.replace("Z", "+00:00")
            )
        except:
            continue

        diff = kickoff_dt - now

        # apenas jogos que começam em até 1 hora
        if not (timedelta(minutes=0) < diff <= timedelta(hours=1)):
            continue

        kickoff = kickoff_dt.strftime("%H:%M")

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
                "kickoff": kickoff,
                "market": market,
                "prob": round(prob * 100, 2),
                "odd": round(random.uniform(1.60, 2.20), 2)
            })

    if not bets:

        print("⚠ Nenhuma aposta encontrada")
        return

    bets = sorted(bets, key=lambda x: x["prob"], reverse=True)

    best_bets = bets[:MAX_BETS]

    print(f"🎯 {len(best_bets)} apostas selecionadas")

    for bet in best_bets:
        send_bet_message(bet)

    print("📤 Mensagens enviadas para Telegram")


if __name__ == "__main__":
    run_pipeline()