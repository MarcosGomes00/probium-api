import json
import os
import requests

API_KEY_ODDS = "6a1c0078b3ed09b42fbacee8f07e7cc3"
HISTORY_FILE = "bets_history.json"

def check_results():
    if not os.path.exists(HISTORY_FILE):
        return

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            bets = json.load(f)
    except Exception as e:
        print("Erro ao ler JSON:", e)
        return

    modificado = False
    ligas_ativas = set(b.get("sport_key") for b in bets if not b.get("checked", True) and "sport_key" in b)

    for liga in ligas_ativas:
        # Busca resultados dos últimos 3 dias dessa liga
        url = f"https://api.the-odds-api.com/v4/sports/{liga}/scores/"
        params = {"apiKey": API_KEY_ODDS, "daysFrom": 3}
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200: continue
            scores_data = resp.json()
            
            # Transforma em um dicionario para busca rápida
            resultados_dict = {jogo["id"]: jogo for jogo in scores_data}

            for bet in bets:
                # Verifica se é dessa liga e se ainda não foi checado
                if bet.get("sport_key") == liga and not bet.get("checked"):
                    jogo_id = bet.get("id")
                    
                    if jogo_id in resultados_dict:
                        jogo = resultados_dict[jogo_id]
                        if jogo.get("completed"): # Jogo acabou!
                            placar = jogo.get("scores")
                            
                            if placar:
                                home_score = 0
                                away_score = 0
                                for time in placar:
                                    if time["name"] == bet["home"]: home_score = int(time["score"])
                                    if time["name"] == bet["away"]: away_score = int(time["score"])
                                
                                # A aposta sempre é vitória da CASA neste nosso robô
                                stake = float(bet.get("stake", 1.0))
                                odd = float(bet.get("odd", 1.0))

                                if home_score > away_score:
                                    bet["result"] = "GREEN"
                                    bet["profit"] = (odd * stake) - stake # Lucro limpo
                                else:
                                    bet["result"] = "RED"
                                    bet["profit"] = -stake # Perdeu a aposta
                                
                                bet["checked"] = True
                                modificado = True
                                print(f"✅ Resultado coletado: {bet['home']} x {bet['away']} -> {bet['result']}")
        except Exception as e:
            print(f"Erro ao checar placar da liga {liga}: {e}")

    # Salva apenas se houve alguma alteração
    if modificado:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(bets, f, indent=2)