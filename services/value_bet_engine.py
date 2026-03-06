def calculate_ev(probability, odds):

    return (probability * odds) - 1


def find_value(probabilities, odds):

    values = {}

    for key in probabilities:

        prob = probabilities[key]
        odd = odds.get(key)

        if odd:

            ev = calculate_ev(prob, odd)

            values[key] = {

                "prob": prob,
                "odd": odd,
                "ev": round(ev, 3)

            }

    return values