from services.bet_scanner import run_scanner

bets = run_scanner()

print("\nRESULTADO DO SCANNER\n")

if not bets:
    print("Nenhuma oportunidade encontrada.")
else:

    for b in bets:

        print(f"{b.home} x {b.away}")
        print("Liga:", b.league)
        print("Mercado:", b.market)
        print("Odd:", b.odd)
        print("Prob:", round(b.prob * 100, 2), "%")
        print("EV:", round(b.ev * 100, 2), "%")
        print("Edge:", round(b.edge * 100, 2), "%")
        print("------")