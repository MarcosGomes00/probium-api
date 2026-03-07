import math


# =========================
# POISSON BASE
# =========================

def poisson_probability(lmbda, k):

    lmbda = float(lmbda)

    return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)


# =========================
# OVER 2.5 GOALS
# =========================

def over25_prob(home_lambda, away_lambda):

    home_lambda = float(home_lambda)
    away_lambda = float(away_lambda)

    prob = 0

    for i in range(6):

        for j in range(6):

            p = poisson_probability(home_lambda, i) * poisson_probability(away_lambda, j)

            if i + j > 2:

                prob += p

    return prob


# =========================
# BOTH TEAMS SCORE
# =========================

def btts_prob(home_lambda, away_lambda):

    home_lambda = float(home_lambda)
    away_lambda = float(away_lambda)

    prob = 0

    for i in range(1, 6):

        for j in range(1, 6):

            prob += poisson_probability(home_lambda, i) * poisson_probability(away_lambda, j)

    return prob


# =========================
# MATCH SCORE PROBABILITY
# =========================

def match_prediction(home_lambda, away_lambda):

    home_lambda = float(home_lambda)
    away_lambda = float(away_lambda)

    results = {}

    for i in range(5):

        for j in range(5):

            p = poisson_probability(home_lambda, i) * poisson_probability(away_lambda, j)

            results[f"{i}-{j}"] = round(p, 4)

    return results