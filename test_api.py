import requests

API_KEY = "1cd3cb39658509019bdb1cdffff22c39"

url = "https://v3.football.api-sports.io/fixtures"

headers = {
    "x-apisports-key": API_KEY
}

params = {
    "league": 39,
    "season": 2024
}

response = requests.get(url, headers=headers, params=params)

data = response.json()

print("status:", data["results"])