import requests
from config import Config
from datetime import datetime, timedelta

def analisa_ultimos_5(id_time, headers):
    """Busca os ultimos 5 jogos gerais do time (Como ele vem na temporada)"""
    url = f"https://v3.football.api-sports.io/fixtures?team={id_time}&last=5"
    jogos = requests.get(url, headers=headers).json().get("response", [])
    
    gols_feitos, gols_sofridos, jogos_over, jogos_btts, vitorias = 0, 0, 0, 0, 0
    for j in jogos:
        g_home, g_away = j["goals"]["home"], j["goals"]["away"]
        if g_home is None: continue
        
        total = g_home + g_away
        if total > 2.5: jogos_over += 1
        if g_home > 0 and g_away > 0: jogos_btts += 1
        
        eh_casa = j["teams"]["home"]["id"] == id_time
        if eh_casa:
            if g_home > g_away: vitorias += 1
            gols_feitos += g_home
            gols_sofridos += g_away
        else:
            if g_away > g_home: vitorias += 1
            gols_feitos += g_away
            gols_sofridos += g_home
            
    return {"over_taxa": jogos_over/5, "btts_taxa": jogos_btts/5, "vitoria_taxa": vitorias/5}

def motor_deep_analysis_diario():
    """Faz a varredura da deep-web dos stats de futebol pro dia"""
    headers = {"x-apisports-key": Config.API_FOOTBALL_KEY}
    hoje = datetime.now().strftime("%Y-%m-%d")
    url = "https://v3.football.api-sports.io/fixtures"
    
    jogos_do_dia = requests.get(url, headers=headers, params={"date": hoje, "timezone": "America/Sao_Paulo"}).json().get("response", [])
    
    ligas_premium = [1, 2, 13, 39, 71, 140, 135, 78, 61]
    lista_ouro = []

    for j in jogos_do_dia:
        if j["league"]["id"] in ligas_premium and j["fixture"]["status"]["short"] == "NS":
            fix_id = j["fixture"]["id"]
            casa_id, fora_id = j["teams"]["home"]["id"], j["teams"]["away"]["id"]
            nome_casa, nome_fora = j["teams"]["home"]["name"], j["teams"]["away"]["name"]
            
            # Cruzando como vêm jogando ultimamente na vida real
            fase_casa = analisa_ultimos_5(casa_id, headers)
            fase_fora = analisa_ultimos_5(fora_id, headers)
            
            # Médias de Tendência Matemática
            media_vitoria_casa = fase_casa["vitoria_taxa"]
            media_over = (fase_casa["over_taxa"] + fase_fora["over_taxa"]) / 2
            media_btts = (fase_casa["btts_taxa"] + fase_fora["btts_taxa"]) / 2

            mercado, prob = None, 0
            
            # Definição Criteriosa (Mínimo de 80% de reincidência para ser call validada)
            if media_vitoria_casa >= 0.80:
                mercado, mercado_codigo = f"Vitória - {nome_casa}", "HOME"
                prob = media_vitoria_casa * 100
            elif media_over >= 0.80:
                mercado, mercado_codigo = "Mais de 2.5 Gols", "OVER25"
                prob = media_over * 100
            elif media_btts >= 0.80:
                mercado, mercado_codigo = "Ambas Equipes Marcam (SIM)", "BTTS"
                prob = media_btts * 100
            
            if mercado:
                lista_ouro.append({
                    "fix_id": fix_id, "jogo": f"{nome_casa} x {nome_fora}",
                    "horario": j["fixture"]["date"], "mercado": mercado, 
                    "mercado_codigo": mercado_codigo, "prob": round(prob, 1),
                    "odd": round((100/prob)+0.35, 2)
                })

    # Retorna as 3 mais prováveis (Highest EV Edge)
    lista_ouro.sort(key=lambda x: x["prob"], reverse=True)
    return lista_ouro[:3]