def resolver_aposta(market, home, away):

    if market == "OVER 2.5":
        return "GREEN" if home + away > 2 else "RED"

    if market == "BTTS YES":
        return "GREEN" if home > 0 and away > 0 else "RED"

    return "RED"