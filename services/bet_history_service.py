from models.bet_history import BetHistory
from services.database import db


def save_bet_history(home, away, league, market, odd, probability, ev):

    bet = BetHistory(

        home=home,
        away=away,
        league=league,
        market=market,
        odd=odd,
        probability=probability,
        ev=ev

    )

    db.session.add(bet)
    db.session.commit()