from services.history_engine import calculate_roi

def bar(prob):

    size=int(prob*20)

    return "█"*size+"░"*(20-size)


def print_bets(bets):

    print("\n🌍 PROBIUM V5 PRO")
    print("════════════════════════════════════")

    if not bets:

        print("Nenhuma aposta encontrada")

        return

    for i,b in enumerate(bets,1):

        prob=round(b["prob"]*100,2)

        ev=round(b["ev"]*100,2)

        print(f"""
🏆 PICK {i}

⚽ {b['home']} vs {b['away']}
🏆 {b['league']}
🕒 {b['kickoff']}

Placar previsto: {b['score']}

Odd: {b['odd']}

Probabilidade
[{bar(b['prob'])}] {prob}%

EV: +{ev}%

Over2.5 {round(b['over25']*100,1)}%
BTTS {round(b['btts']*100,1)}%

Confiança: {b['confidence']}
Stake: {b['stake']}%
""")

    print(f"\nROI histórico: {calculate_roi()}%\n")