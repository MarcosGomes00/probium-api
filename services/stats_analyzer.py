import requests

# Sua chave da API-Football
API_KEY_FOOTBALL = "1cd3cb39658509019bdb1cdffff22c39"

def check_advanced_stats(home_team, away_team):
    """
    1. Verifica o histórico de confronto direto (H2H) entre os dois times.
    2. Verifica a fase recente do time mandante.
    """
    headers = {
        "x-apisports-key": API_KEY_FOOTBALL
    }
    
    try:
        # 1. Buscar os IDs dos dois times
        search_url = "https://v3.football.api-sports.io/teams"
        home_resp = requests.get(search_url, headers=headers, params={"search": home_team}, timeout=10).json()
        away_resp = requests.get(search_url, headers=headers, params={"search": away_team}, timeout=10).json()
        
        # Se os nomes dos times não baterem na API, aprova a aposta para o bot não parar de funcionar
        if not home_resp.get("response") or not away_resp.get("response"):
            return True 
            
        home_id = home_resp["response"][0]["team"]["id"]
        away_id = away_resp["response"][0]["team"]["id"]
        
        # =========================================================
        # FILTRO A: CONFRONTO DIRETO (H2H)
        # =========================================================
        h2h_url = "https://v3.football.api-sports.io/fixtures/headtohead"
        h2h_params = {"h2h": f"{home_id}-{away_id}", "last": 5}
        h2h_data = requests.get(h2h_url, headers=headers, params=h2h_params, timeout=10).json()
        
        vitorias_visitante_h2h = 0
        
        for match in h2h_data.get("response", []):
            if match["teams"]["away"]["id"] == away_id and match["teams"]["away"]["winner"] is True:
                vitorias_visitante_h2h += 1
            elif match["teams"]["home"]["id"] == away_id and match["teams"]["home"]["winner"] is True:
                vitorias_visitante_h2h += 1
                
        # Se o Visitante ganhou 4 ou 5 dos últimos 5 confrontos contra o Mandante (Carrasco histórico)
        if vitorias_visitante_h2h >= 4:
            print(f"⚠️ ARMADILHA H2H: O {away_team} é carrasco do {home_team}!")
            return False

        # =========================================================
        # FILTRO B: FORMA RECENTE DO MANDANTE
        # =========================================================
        fix_url = "https://v3.football.api-sports.io/fixtures"
        fix_params = {"team": home_id, "last": 5}
        fix_data = requests.get(fix_url, headers=headers, params=fix_params, timeout=10).json()
        
        home_derrotas = 0
        for match in fix_data.get("response", []):
            if match["teams"]["home"]["id"] == home_id and match["teams"]["home"]["winner"] is False:
                home_derrotas += 1
            elif match["teams"]["away"]["id"] == home_id and match["teams"]["away"]["winner"] is False:
                home_derrotas += 1
                
        # Se o Mandante perdeu 4 ou 5 dos últimos 5 jogos
        if home_derrotas >= 4:
            print(f"⚠️ ARMADILHA FASE: {home_team} perdeu {home_derrotas} dos últimos 5 jogos!")
            return False
            
        return True # APOSTA SUPER APROVADA PELOS FILTROS AVANÇADOS!

    except Exception as e:
        print(f"⚠️ Erro ao buscar dados históricos de {home_team} x {away_team}: {e}")
        return True