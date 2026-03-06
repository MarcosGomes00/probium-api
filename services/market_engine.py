def calculate_markets(matrix):

    home_win = 0
    draw = 0
    away_win = 0

    over_2_5 = 0
    under_2_5 = 0

    for i in range(len(matrix)):
        for j in range(len(matrix[i])):

            prob = matrix[i][j]

            if i > j:
                home_win += prob

            elif i == j:
                draw += prob

            else:
                away_win += prob

            if i + j > 2:
                over_2_5 += prob
            else:
                under_2_5 += prob

    return {
        "home_win": home_win,
        "draw": draw,
        "away_win": away_win,
        "over_2_5": over_2_5,
        "under_2_5": under_2_5
    }