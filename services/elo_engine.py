import math

HOME_ADVANTAGE = 65

def elo_probability(elo_home, elo_away):

    diff = (elo_home + HOME_ADVANTAGE) - elo_away

    prob = 1 / (1 + math.pow(10, -diff / 400))

    return prob