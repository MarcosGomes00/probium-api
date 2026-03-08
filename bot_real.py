import requests
import time
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# Importar o verificador de resultados (Vamos criar no Passo 2)
try:
    from services.result_checker import check_results
except ImportError:
    def check_results():
        pass # Evita erro se o arquivo ainda não existir

# Configurações Reais
API_KEY_ODDS = "6a1c0078b3ed09b42fbacee8f07e7cc3"
TELEGRAM_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A" # Bot 1
CHAT_ID = "-1003814625223"
HISTORY_FILE = "bets_history.json"

# Ligas incluindo NBA
LIGAS =[
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_brazil_campeonato",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga",
    "basketball_nba" # NOVO: Adicionado NBA
]

jogos_enviados = set()

def salvar_historico(bet_data):
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                bets = json.load(f)
        else:
            bets = []
    except:
        bets =[]

    bets.append(bet_data)

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(bets, f, indent=2)

def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar pro Telegram: {e}")

def processar_jogos_e_enviar():
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    print(f"\n🔄[ATUALIZAÇÃO - {agora_br.strftime('%H:%M:%S')}] Buscando jogos reais (Futebol & NBA)...")

    for liga in LIGAS:
        url = f"https://api.the-odds-api.com/v4/sports/{liga}/odds/"
        parametros = {
            "apiKey": API_KEY_ODDS,
            "regions": "eu,uk,us",
            "markets": "h2h",
            "bookmakers": "bet365,pinnacle"
        }

        try:
            resposta = requests.get(url, params=parametros, timeout=15)
            if resposta.status_code != 200: continue
            dados = resposta.json()

            for evento in dados:
                horario_utc = datetime.fromisoformat(evento["commence_time"].replace("Z", "+00:00"))
                horario_br = horario_utc.astimezone(ZoneInfo("America/Sao_Paulo"))
                
                if horario_br < agora_br: continue
                
                bookmakers = evento.get("bookmakers",[])
                if not bookmakers: continue
                mercados = bookmakers[0].get("markets",[])
                if not mercados: continue
                
                odds = mercados[0]["outcomes"]
                home_team = evento["home_team"]
                away_team = evento["away_team"]
                is_nba = "basketball" in liga
                
                odd_home = next((item["price"] for item in odds if item["name"] == home_team), 0)
                if odd_home == 0: continue

                # 6️⃣ FILTRO ANTI-ARMADILHA (Ignora odds esmagadas ou improváveis demais)
                if odd_home < 1.25 or odd_home > 2.50:
                    continue 

                prob = 1 / odd_home
                ev = prob * 0.12 
                edge = ev / 2

                # Se for NBA, ajusta a confiança
                if is_nba:
                    if odd_home <= 1.65: confianca = "🏀🔥 ELITE NBA"; stake = 2.0
                    else: confianca = "🏀💪 FORTE NBA"; stake = 1.0
                else:
                    if odd_home <= 1.55: confianca = "⚽🔥 ELITE"; stake = 2.0
                    elif odd_home <= 1.85: confianca = "⚽💪 FORTE"; stake = 1.5
                    else: confianca = "⚽👍 BOA"; stake = 1.0
                
                jogo_id = f"{evento['id']}" # Usando ID oficial para checar depois
                minutos_faltando = (horario_br - agora_br).total_seconds() / 60

                if 30 <= minutos_faltando <= 60:
                    if jogo_id not in jogos_enviados:
                        
                        texto_msg = (
                            f"💎 <b>APOSTA PREMIUM LIBERADA</b> 💎\n\n"
                            f"🏆 <b>Liga:</b> {evento['sport_title']}\n"
                            f"⏰ <b>Horário:</b> {horario_br.strftime('%H:%M')} (Faltam {int(minutos_faltando)} min)\n"
                            f"{'🏀' if is_nba else '⚽️'} <b>Jogo:</b> {home_team} x {away_team}\n\n"
                            f"🎯 <b>O QUE APOSTAR:</b>\n"
                            f"👉 <b>Vitória do {home_team} (Casa)</b>\n\n"
                            f"📈 <b>Odd Mínima:</b> {odd_home}\n"
                            f"💰 <b>Gestão / Stake:</b> {stake} Unidades\n"
                            f"🔥 <b>Confiança:</b> {confianca}\n\n"
                            f"<i>⚠️ Siga a gestão e jogue com responsabilidade.</i>"
                        )
                        
                        enviar_telegram(texto_msg)
                        
                        # Salva histórico detalhado para o Dashboard
                        salvar_historico({
                            "id": jogo_id,
                            "sport_key": liga,
                            "home": home_team,
                            "away": away_team,
                            "league": evento["sport_title"],
                            "odd": odd_home,
                            "prob": prob,
                            "ev": ev,
                            "stake": stake,
                            "checked": False,
                            "result": None,
                            "profit": 0,
                            "date": horario_br.strftime('%d/%m/%Y')
                        })

                        jogos_enviados.add(jogo_id)
                        print(f"🚀 Análise enviada: {home_team} x {away_team}")

        except Exception as e:
            print("Erro na API de Odds:", e)

if __name__ == "__main__":
    print("🤖 Bot de Análises Reais + NBA Iniciado!")
    while True:
        processar_jogos_e_enviar()
        
        # Chama a checagem de resultados reais
        try:
            print("🔍 Verificando bilhetes anteriores...")
            check_results()
        except Exception as e:
            print(f"Erro ao checar resultados: {e}")
            
        time.sleep(600)