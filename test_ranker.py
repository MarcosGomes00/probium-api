import json
from services.opportunity_ranker import rank_opportunities

with open("bets_history.json") as f:
    bets = json.load(f)

top = rank_opportunities(bets)

print("\nTOP 3 OPORTUNIDADES\n")

for b in top:

    print(b["home"], "x", b["away"])
    print("Mercado:", b["market"])
    print("Odd:", b["odd"])
    print("Score:", round(b["final_score"], 3))
    print("------")