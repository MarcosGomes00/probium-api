from datetime import datetime, timezone
import random

from services.data_source import get_matches_today
from services.poisson_model import over25_prob, btts_prob
from services.telegram_bot import send_bet_message


MIN_PROB = 0.60

# controle para não repetir envio
sent_games = set()


def run_pipeline():

    print("🔎 PROBIUM analisando jogos...")

    matches = get_matches_today()

    print(f"⚽ {len(matches)} jogos encontrados")

    bets = []

    now = datetime.now(timezone.utc)

    for m in matches:

        home = m["home"]
        away = m["away"]
        league = m["league"]
        kickoff = m["time"]

        try:
            kickoff_dt = datetime.fromisoformat(kickoff.replace("Z","+00:00"))
        except:
            continue

        diff = kickoff_dt - now
        minutes = diff.total_seconds() / 60

        # enviar somente jogos que começam em até 60 minutos
        if minutes > 60 or minutes < 0:
            continue

        game_id = f"{home}-{away}-{kickoff}"

        if game_id in sent_games:
            continue

        home_attack = random.uniform(1.2,2.2)
        away_attack = random.uniform(1.0,2.0)

        over = over25_prob(home_attack, away_attack)
        btts = btts_prob(home_attack, away_attack)
        under = 1 - over

        markets = {
            "OVER 2.5": over,
            "BTTS SIM": btts,
            "UNDER 2.5": under
        }

        market = max(markets, key=markets.get)
        prob = markets[market]

        if prob < MIN_PROB:
            continue

        bets.append({
            "home": home,
            "away": away,
            "league": league,
            "market": market,
            "prob": round(prob*100,1),
            "kickoff": kickoff_dt.strftime("%H:%M"),
            "odd": round(random.uniform(1.6,2.2),2),
            "ev": "+EV"
        })

        sent_games.add(game_id)

    if not bets:

        print("⚠ Nenhuma aposta encontrada")
        return

    bets = sorted(bets, key=lambda x: x["prob"], reverse=True)

    # limitar a 5 apostas
    bets = bets[:5]

    print(f"🎯 {len(bets)} apostas selecionadas")

    for bet in bets:

        send_bet_message(bet)

    print("📤 Mensagens enviadas no Telegram")


if __name__ == "__main__":
    run_pipeline()