import math


def poisson_probability(lmbda, k):
    return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)


def calculate_goal_matrix(home_xg, away_xg, max_goals=5):

    matrix = []

    for home_goals in range(max_goals + 1):
        row = []
        for away_goals in range(max_goals + 1):

            home_prob = poisson_probability(home_xg, home_goals)
            away_prob = poisson_probability(away_xg, away_goals)

            row.append(home_prob * away_prob)

        matrix.append(row)

    return matrix


def calculate_match_probabilities(matrix):

    home_win = 0
    draw = 0
    away_win = 0

    for i in range(len(matrix)):
        for j in range(len(matrix)):

            if i > j:
                home_win += matrix[i][j]

            elif i == j:
                draw += matrix[i][j]

            else:
                away_win += matrix[i][j]

    return home_win, draw, away_win