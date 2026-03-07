from services.probium_pipeline import run_pipeline
from services.opportunity_ranker import rank_opportunities


def main():

    print("\nExecutando pipeline...\n")

    bets = run_pipeline()

    if not bets:
        print("Nenhuma aposta encontrada.")
        return

    print("Total encontrado:", len(bets))

    top = rank_opportunities(bets)

    print("\nTOP 3 OPORTUNIDADES\n")

    for b in top:

        home = b.get("home")
        away = b.get("away")

        print(home, "x", away)

        print("Mercado:", b["market"])
        print("Odd:", b["odd"])
        print("Prob:", round(b["prob"] * 100, 2), "%")
        print("EV:", round(b["ev"] * 100, 2), "%")

        print("------")


if __name__ == "__main__":
    main()