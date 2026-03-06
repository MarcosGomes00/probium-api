def rank_bets(bets):

    for b in bets:

        b["rank_score"] = (b["prob"]*50)+(b["ev"]*30)+(b["edge"]*20)

    bets.sort(key=lambda x:x["rank_score"], reverse=True)

    return bets