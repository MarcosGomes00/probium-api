from services.probium_v2_pro_scanner import run_probium_v2_pro

bets = run_probium_v2_pro()

print("RESULTADO DO SCANNER\n")

for b in bets:

    print("Jogo:", b.home, "x", b.away)
    print("Odd:", b.odd)
    print("EV:", round(b.ev * 100, 2), "%")
    print("Liga:", b.league)
    print("------")