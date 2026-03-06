import random
from services.form_engine import FormEngine


class HistoricalEngine:

    def __init__(self):

        self.form_engine = FormEngine()


    def h2h_factor(self):

        return random.uniform(0.45, 0.65)


    def attack_strength(self):

        return random.uniform(0.45, 0.75)


    def defense_strength(self):

        return random.uniform(0.40, 0.70)


    def combined_probability(
        self,
        elo_prob,
        poisson_prob,
        home,
        away
    ):

        form = self.form_engine.team_form_probability()

        h2h = self.h2h_factor()

        attack = self.attack_strength()

        defense = self.defense_strength()

        prob = (

            (elo_prob * 0.30)
            + (poisson_prob * 0.20)
            + (form * 0.20)
            + (h2h * 0.15)
            + (attack * 0.10)
            + (defense * 0.05)

        )

        prob = max(0.40, min(0.85, prob))

        return prob