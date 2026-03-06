from .api_football import get_api_football_data
from .understat import get_understat_data
from .sofascore import get_sofascore_data
from .flashscore import get_flashscore_data
from .football_data import get_football_data


def collect_match_data(team):

    sources = [
        get_api_football_data,
        get_understat_data,
        get_sofascore_data,
        get_flashscore_data,
        get_football_data
    ]

    results = []

    for source in sources:
        try:
            data = source(team)

            if data:
                results.extend(data)

        except Exception:
            continue

    return results