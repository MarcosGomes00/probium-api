from models.match import Match
from services.database import db


def team_stats(team):

    home_matches = Match.query.filter_by(home_team=team).all()
    away_matches = Match.query.filter_by(away_team=team).all()

    games = len(home_matches) + len(away_matches)

    if games == 0:
        return {
            "attack": 1,
            "defense": 1
        }

    goals_scored = 0
    goals_conceded = 0

    for m in home_matches:
        goals_scored += int(m.home_goals or 0)
        goals_conceded += int(m.away_goals or 0)

    for m in away_matches:
        goals_scored += int(m.away_goals or 0)
        goals_conceded += int(m.home_goals or 0)

    attack = goals_scored / games
    defense = goals_conceded / games

    return {
        "attack": attack,
        "defense": defense
    }