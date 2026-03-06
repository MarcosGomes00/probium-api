import math


def poisson_probability(k, lamb):

    lamb = float(lamb)

    return (lamb ** k * math.exp(-lamb)) / math.factorial(k)


def match_prediction(home_attack, away_attack):

    home_attack = float(home_attack)
    away_attack = float(away_attack)

    home_goals = []
    away_goals = []

    for i in range(6):

        home_goals.append(poisson_probability(i, home_attack))
        away_goals.append(poisson_probability(i, away_attack))

    home_win = 0
    draw = 0
    away_win = 0

    for i in range(6):
        for j in range(6):

            prob = home_goals[i] * away_goals[j]

            if i > j:
                home_win += prob

            elif i == j:
                draw += prob

            else:
                away_win += prob

    return {
        "home_win": round(home_win, 4),
        "draw": round(draw, 4),
        "away_win": round(away_win, 4)
    }


def predict_score(home_attack, away_attack):

    result = match_prediction(home_attack, away_attack)

    return result


def over25_prob(home_attack, away_attack):

    total_lambda = float(home_attack) + float(away_attack)

    prob = 0

    for goals in range(3):
        prob += poisson_probability(goals, total_lambda)

    return round(1 - prob, 4)


def btts_prob(home_attack, away_attack):

    prob_home_zero = poisson_probability(0, home_attack)
    prob_away_zero = poisson_probability(0, away_attack)

    prob = 1 - prob_home_zero - prob_away_zero + (prob_home_zero * prob_away_zero)

    return round(prob, 4)