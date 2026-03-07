from datetime import datetime, timezone
from collections import defaultdict

from services.data_source import get_matches_today
from services.poisson_model import over25_prob, btts_prob
from services.telegram_bot import send_bet_message
from services.probium_engine_v7 import analyze_match


MIN_PROB = 0.60

# evita repetir jogos
sent_games = set()


def run_pipeline():

    print("🔎 PROBIUM analisando jogos...")

    matches = get_matches_today()

    print(f"⚽ {len(matches)} jogos encontrados")

    now = datetime.now(timezone.utc)

    bets_by_hour = defaultdict(list)

    for m in matches:

        home = m.get("home")
        away = m.get("away")
        league = m.get("league")
        kickoff = m.get("time")

        if not kickoff:
            continue

        try:
            kickoff_dt = datetime.fromisoformat(kickoff.replace("Z", "+00:00"))
        except:
            continue

        diff = kickoff_dt - now
        minutes = diff.total_seconds() / 60

        # só jogos até 1h antes
        if minutes > 60 or minutes < 0:
            continue

        game_id = f"{home}-{away}-{kickoff}"

        if game_id in sent_games:
            continue

        # =========================
        # ANALISE V7
        # =========================

        try:

            market, prob = analyze_match(m)

        except:

            # fallback Poisson caso API falhe
            home_attack = 1.5
            away_attack = 1.4

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

        bet = {

            "home": home,
            "away": away,
            "league": league,
            "market": market,
            "prob": round(prob * 100, 1),
            "kickoff": kickoff_dt.strftime("%H:%M"),
            "odd": 1.85,
            "ev": "+EV"

        }

        bets_by_hour[bet["kickoff"]].append(bet)

        sent_games.add(game_id)

    if not bets_by_hour:

        print("⚠ Nenhuma aposta encontrada")
        return

    total_sent = 0

    for hour, bets in bets_by_hour.items():

        # ordenar apostas do horário
        bets = sorted(bets, key=lambda x: x["prob"], reverse=True)

        # enviar apenas top 3 daquele horário
        top_bets = bets[:3]

        print(f"🎯 {len(top_bets)} apostas para {hour}")

        for bet in top_bets:

            send_bet_message(bet)

            total_sent += 1

    print(f"📤 {total_sent} apostas enviadas no Telegram")


if __name__ == "__main__":
    run_pipeline()