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