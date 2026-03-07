def calculate_ev(prob, odd):

    implied_prob = 1 / odd

    value = prob - implied_prob

    return round(value * 100, 2)