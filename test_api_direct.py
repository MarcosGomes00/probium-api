import requests

API_KEY = "1cd3cb39658509019bdb1cdffff22c39"

url = "https://v3.football.api-sports.io/fixtures"

headers = {
    "x-apisports-key": API_KEY
}

params = {
    "next": 10
}

response = requests.get(url, headers=headers, params=params)

print("Status code:", response.status_code)

data = response.json()

print("Results:", data.get("results"))

if data.get("response"):
    for g in data["response"][:5]:
        print(
            g["teams"]["home"]["name"],
            "x",
            g["teams"]["away"]["name"],
            "-",
            g["league"]["name"]
        )