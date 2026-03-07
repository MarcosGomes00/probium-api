from typing import List, Dict


def choose_market(bet: Dict) -> str:

    over = bet.get("over25", 0)
    btts = bet.get("btts", 0)

    if over > 0.60:
        return "OVER 2.5"

    if btts > 0.60:
        return "BTTS YES"

    return "HOME WIN"


def confidence_weight(label: str) -> float:

    weights = {
        "🔥 ELITE": 1.0,
        "💪 FORTE": 0.8,
        "👍 BOA": 0.6
    }

    return weights.get(label, 0.5)


def calculate_score(bet: Dict) -> float:

    prob = bet.get("prob", 0)
    ev = bet.get("ev", 0)
    edge = bet.get("edge", 0)

    weight = confidence_weight(bet.get("confidence"))

    score = (
        prob * 0.40 +
        ev * 0.30 +
        edge * 0.20 +
        weight * 0.10
    )

    return score


def filter_bets(bets: List[Dict]) -> List[Dict]:

    filtered = []

    for b in bets:

        if b.get("prob", 0) < 0.60:
            continue

        if b.get("ev", 0) < 0.05:
            continue

        if b.get("edge", 0) < 0.04:
            continue

        odd = b.get("odd", 0)

        if odd < 1.40 or odd > 2.20:
            continue

        filtered.append(b)

    return filtered


def rank_opportunities(bets: List[Dict], top_n: int = 3) -> List[Dict]:

    bets = filter_bets(bets)

    for b in bets:

        b["market"] = choose_market(b)

        b["final_score"] = calculate_score(b)

    bets.sort(key=lambda x: x["final_score"], reverse=True)

    return bets[:top_n]