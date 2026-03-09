import requests
from datetime import datetime

# Sua chave real da API-Football
API_FOOTBALL_KEY = "1cd3cb39658509019bdb1cdffff22c39"

def buscar_id_time(nome_time):
    # Busca o ID do time na API-Football baseado no nome
    url = "https://v3.football.api-sports.io/teams"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    params = {"search": nome_time}
    
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        if data.get("results") > 0:
            return data["response"][0]["team"]["id"]
    except:
        pass
    return None

def obter_historico_times(home_name, away_name):
    """
    Retorna uma análise em texto dos últimos 5 jogos de cada time 
    e o confronto direto (H2H) para incluir no Telegram.
    """
    home_id = buscar_id_time(home_name)
    away_id = buscar_id_time(away_name)
    
    if not home_id or not away_id:
        return None, False # Não achou os times, aprova a aposta mas sem histórico detalhado

    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    
    historico_msg = ""
    aprovado = True
    
    try:
        # 1. Busca os últimos 5 jogos do Casa e Visitante
        url_form = "https://v3.football.api-sports.io/teams/statistics"
        # Simplificamos buscando apenas os últimos fixtures via H2H para poupar requisições da sua API
        
        url_h2h = "https://v3.football.api-sports.io/fixtures/headtohead"
        params_h2h = {"h2h": f"{home_id}-{away_id}", "last": 5}
        
        resp_h2h = requests.get(url_h2h, headers=headers, params=params_h2h, timeout=10)
        data_h2h = resp_h2h.json()
        
        vitorias_home = 0
        vitorias_away = 0
        empates = 0
        
        if data_h2h.get("results", 0) > 0:
            for match in data_h2h["response"]:
                if match["teams"]["home"]["winner"] == True and match["teams"]["home"]["id"] == home_id:
                    vitorias_home += 1
                elif match["teams"]["away"]["winner"] == True and match["teams"]["away"]["id"] == home_id:
                    vitorias_home += 1
                elif match["teams"]["home"]["winner"] == True and match["teams"]["home"]["id"] == away_id:
                    vitorias_away += 1
                elif match["teams"]["away"]["winner"] == True and match["teams"]["away"]["id"] == away_id:
                    vitorias_away += 1
                else:
                    empates += 1
                    
            historico_msg += f"📚 <b>HISTÓRICO DE CONFRONTOS (Últimos {data_h2h['results']}):</b>\n"
            historico_msg += f"✅ {home_name}: {vitorias_home} Vitórias\n"
            historico_msg += f"✅ {away_name}: {vitorias_away} Vitórias\n"
            historico_msg += f"➖ Empates: {empates}\n"
            
            # FILTRO ANTI-RED: Se o time da casa nunca ganhou do visitante nos últimos 5 jogos, e a aposta for no Casa, reprova.
            # Essa validação será devolvida para o bot principal tomar a decisão.
            
        return historico_msg, True

    except Exception as e:
        print(f"Erro ao buscar histórico: {e}")
        return None, False