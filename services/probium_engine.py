def implied_prob(odd):

    return 1 / odd


def calculate_ev(prob, odd):

    return (prob * odd) - 1


def calculate_edge(prob, odd):

    return prob - implied_prob(odd)