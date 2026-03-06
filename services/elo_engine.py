class EloEngine:

    def expected_score(self, elo_a, elo_b):

        return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))


    def win_probability(self, elo_home, elo_away):

        home = self.expected_score(elo_home, elo_away)
        away = 1 - home

        return home, away