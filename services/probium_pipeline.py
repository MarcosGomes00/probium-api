import requests
from config import Config
from datetime import datetime, timedelta

def analisar_jogos_e_gerar_bilhetes():
    print("Buscando partidas futuras na API...")
    
    url_fixtures = "https://v3.football.api-sports.io/fixtures"
    url_h2h = "https://v3.football.api-sports.io/fixtures/headtohead"
    headers = {"x-apisports-key": Config.API_FOOTBALL_KEY}
    
    hoje = datetime.now().strftime("%Y-%m-%d")
    futuro = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d")
    
    params_busca = {
        "from": hoje,
        "to": futuro,
        "timezone": "America/Sao_Paulo"
    }
    
    response = requests.get(url_fixtures, headers=headers, params=params_busca)
    jogos = response.json().get("response", [])
    
    if not jogos:
        print("Nenhuma partida encontrada para este período.")
        return []

    ligas_premium = [1, 2, 13, 39, 71, 140, 135, 78, 61] 
    bilhetes_aprovados = []

    for jogo in jogos:
        liga_id = jogo["league"]["id"]
        
        if liga_id in ligas_premium and jogo["fixture"]["status"]["short"] == "NS":
            time_casa = jogo["teams"]["home"]["name"]
            id_casa = jogo["teams"]["home"]["id"]
            time_fora = jogo["teams"]["away"]["name"]
            id_fora = jogo["teams"]["away"]["id"]
            data_hora = jogo["fixture"]["date"]
            
            try:
                h2h_params = {"h2h": f"{id_casa}-{id_fora}", "last": 10}
                resp_h2h = requests.get(url_h2h, headers=headers, params=h2h_params)
                historico = resp_h2h.json().get("response", [])
                
                if not historico: 
                    continue 
                
                vitorias_casa = 0
                gols_totais = 0
                
                for confronto in historico:
                    gol_c = confronto["goals"]["home"]
                    gol_f = confronto["goals"]["away"]
                    if gol_c is not None and gol_f is not None:
                        gols_totais += (gol_c + gol_f)
                        if gol_c > gol_f: 
                            vitorias_casa += 1

                probabilidade = (vitorias_casa / len(historico)) * 100
                media_gols = gols_totais / len(historico)
                
                if probabilidade >= 65.0:
                    bilhetes_aprovados.append({
                        "liga": jogo["league"]["name"],
                        "jogo": f"{time_casa} x {time_fora}",
                        "horario": data_hora,
                        "palpite": f"Vitória do {time_casa}",
                        "prob": round(probabilidade, 1),
                        "odd": round((100 / probabilidade) + 0.35, 2)
                    })
                elif media_gols > 2.7:
                    prob_gols = round((media_gols / 4.0) * 100, 1) if media_gols < 4.0 else 92.0
                    bilhetes_aprovados.append({
                        "liga": jogo["league"]["name"],
                        "jogo": f"{time_casa} x {time_fora}",
                        "horario": data_hora,
                        "palpite": "Total de Gols (Acima de 2.5)",
                        "prob": prob_gols,
                        "odd": round((100 / prob_gols) + 0.40, 2) if prob_gols > 0 else 1.50
                    })
                    
            except Exception as e:
                print(f"Erro ao processar jogo {time_casa} x {time_fora}: {e}")
                continue

    # Retorna as 3 melhores análises encontradas
    return sorted(bilhetes_aprovados, key=lambda x: x["prob"], reverse=True)[:3]