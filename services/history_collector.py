import requests
from config import Config
from services.database import db

API_URL = "https://v3.football.api-sports.io/fixtures"


def fetch_league_history(league_id, season):

    headers = {
        "x-apisports-key": Config.API_FOOTBALL_KEY
    }

    params = {
        "league": league_id,
        "season": season
    }

    r = requests.get(API_URL, headers=headers, params=params, timeout=10)

    data = r.json()

    return data.get("response", [])


def save_match(match):

    fixture = match["fixture"]
    teams = match["teams"]
    goals = match["goals"]
    league = match["league"]

    record = {
        "league": league["name"],
        "season": league["season"],
        "date": fixture["date"],
        "home_team": teams["home"]["name"],
        "away_team": teams["away"]["name"],
        "home_goals": goals["home"],
        "away_goals": goals["away"]
    }

    db.engine.execute(
        """
        INSERT INTO matches_history
        (league, season, date, home_team, away_team, home_goals, away_goals)
        VALUES (:league, :season, :date, :home_team, :away_team, :home_goals, :away_goals)
        """,
        record
    )


def collect_league_history(league_id, season):

    matches = fetch_league_history(league_id, season)

    for match in matches:

        if match["fixture"]["status"]["short"] == "FT":

            save_match(match)


def collect_top_leagues():

    leagues = [
        39,   # Premier League
        140,  # La Liga
        78,   # Bundesliga
        135,  # Serie A
        71,   # Brasileirão
        61    # Ligue 1
    ]

    for league in leagues:

        collect_league_history(league, 2024)