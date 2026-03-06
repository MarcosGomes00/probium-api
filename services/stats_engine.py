import random


class StatsEngine:

    def get_team_stats(self, team):

        # Simulação baseada em dados médios reais do futebol
        # até conectarmos API completa

        goals_scored = random.uniform(1.0, 2.4)
        goals_conceded = random.uniform(0.8, 1.8)

        form = random.uniform(0.3, 0.9)

        return {
            "scored": goals_scored,
            "conceded": goals_conceded,
            "form": form
        }