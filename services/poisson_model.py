import math


def poisson_probability(lmbda, k):
    return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)


def match_prediction(home_attack, home_defense, away_attack, away_defense):

    home_lambda = home_attack * away_defense
    away_lambda = away_attack * home_defense

    home_win = 0
    draw = 0
    away_win = 0

    for i in range(6):
        for j in range(6):

            p = poisson_probability(home_lambda, i) * poisson_probability(away_lambda, j)

            if i > j:
                home_win += p
            elif i == j:
                draw += p
            else:
                away_win += p

    return {
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win
    }