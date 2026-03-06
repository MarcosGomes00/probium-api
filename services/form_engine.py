import random


class FormEngine:

    def __init__(self):
        pass


    def last_results(self):

        """
        Simula últimos 5 jogos
        """

        results = []

        for _ in range(5):

            results.append(random.choice(["W", "D", "L"]))

        return results


    def form_score(self, results):

        score = 0

        for r in results:

            if r == "W":
                score += 3

            elif r == "D":
                score += 1

        return score / 15


    def team_form_probability(self):

        results = self.last_results()

        score = self.form_score(results)

        prob = 0.45 + (score * 0.35)

        return min(prob, 0.75)