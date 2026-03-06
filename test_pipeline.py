from services.probium_pipeline import run_pipeline
from services.display_engine import print_bets

def main():

    bets = run_pipeline()

    print_bets(bets)


if __name__ == "__main__":
    main()