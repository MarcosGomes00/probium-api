import math


def poisson_prob(lmbda, k):

    return (lmbda**k * math.exp(-lmbda)) / math.factorial(k)


def expected_goals(home_attack, away_defense):

    return (home_attack + away_defense) / 2


def over25_prob(home_attack, away_attack):

    lam = home_attack + away_attack

    p0 = poisson_prob(lam, 0)
    p1 = poisson_prob(lam, 1)
    p2 = poisson_prob(lam, 2)

    return 1 - (p0 + p1 + p2)


def btts_prob(home_attack, away_attack):

    p_home = 1 - poisson_prob(home_attack, 0)
    p_away = 1 - poisson_prob(away_attack, 0)

    return p_home * p_away