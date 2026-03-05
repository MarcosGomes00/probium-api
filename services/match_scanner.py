import requests


def get_today_matches():

    # exemplo inicial (mock)
    # depois podemos ligar em API real

    matches = [

        {
            "home": "Barcelona",
            "away": "Real Madrid"
        },

        {
            "home": "Manchester City",
            "away": "Liverpool"
        },

        {
            "home": "Bayern Munich",
            "away": "Dortmund"
        }

    ]

    return matches