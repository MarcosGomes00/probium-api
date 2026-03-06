from config import Config
from services.probium_scanner import run_scanner

bets = run_scanner(Config.ODDS_API_KEY)

print("\nRESULTADO DO SCANNER\n")

for b in bets:

    print(f"{b.home} x {b.away}")
    print("Liga:", b.league)
    print("Mercado:", b.market)
    print("Odd:", b.odd)
    print("EV:", round(b.ev * 100, 2), "%")
    print("------")