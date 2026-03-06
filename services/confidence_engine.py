def confidence_level(prob, ev):

    score = prob + ev

    if score >= 0.80:
        return "🔥 ELITE", 2.0

    if score >= 0.70:
        return "💪 FORTE", 1.5

    if score >= 0.60:
        return "👍 BOA", 1.0

    return "⚠️ BAIXA", 0.5