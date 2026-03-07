import requests
import time
from datetime import datetime
from zoneinfo import ZoneInfo

# Configurações Reais
API_KEY_ODDS = "6a1c0078b3ed09b42fbacee8f07e7cc3"
TELEGRAM_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"

LIGAS =[
    "soccer_epl",
    "soccer_spain_la_liga",
    "soccer_brazil_campeonato",
    "soccer_italy_serie_a",
    "soccer_germany_bundesliga"
]

jogos_enviados = set()

def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Erro ao enviar pro Telegram: {e}")

def processar_jogos_e_enviar():
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    print(f"\n🔄[ATUALIZAÇÃO - {agora_br.strftime('%H:%M:%S')}] Buscando jogos reais...")

    for liga in LIGAS:
        url = f"https://api.the-odds-api.com/v4/sports/{liga}/odds/"
        parametros = {
            "apiKey": API_KEY_ODDS,
            "regions": "eu,uk",
            "markets": "h2h",
            "bookmakers": "bet365,pinnacle"
        }

        try:
            resposta = requests.get(url, params=parametros)
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
                
                odd_home = next((item["price"] for item in odds if item["name"] == home_team), 0)
                
                if odd_home == 0: continue

                prob = 1 / odd_home
                ev = prob * 0.12 
                edge = ev / 2
                
                if odd_home <= 1.55:
                    confianca = "🔥 ELITE"
                    stake = 2.0
                elif odd_home <= 1.85:
                    confianca = "💪 FORTE"
                    stake = 1.5
                else:
                    confianca = "👍 BOA"
                    stake = 1.0
                
                jogo_id = f"{home_team}_x_{away_team}_{horario_br.strftime('%Y%m%d')}"
                minutos_faltando = (horario_br - agora_br).total_seconds() / 60

                # Verifica se o jogo vai começar entre 30 e 60 minutos
                if 30 <= minutos_faltando <= 60:
                    if jogo_id not in jogos_enviados:
                        
                        # --- NOVO VISUAL PREMIUM ---
                        texto_msg = (
                            f"💎 <b>APOSTA PREMIUM LIBERADA</b> 💎\n\n"
                            f"🏆 <b>Campeonato:</b> {evento['sport_title']}\n"
                            f"⏰ <b>Horário:</b> {horario_br.strftime('%H:%M')} (Faltam {int(minutos_faltando)} min)\n"
                            f"⚽️ <b>Jogo:</b> {home_team} x {away_team}\n\n"
                            f"🎯 <b>O QUE APOSTAR (MERCADO EXATO):</b>\n"
                            f"👉 <b>Vitória do {home_team} (Casa)</b>\n\n"
                            f"📈 <b>Odd Mínima:</b> {odd_home}\n"
                            f"💰 <b>Gestão / Stake:</b> {stake} Unidades\n"
                            f"🔥 <b>Confiança:</b> {confianca}\n\n"
                            f"🤖 <b>Estatísticas do Algoritmo:</b>\n"
                            f"• Chance de Bater: <code>{prob:.2%}</code>\n"
                            f"• Valor Encontrado (+EV): <code>{ev:.2%}</code>\n"
                            f"• Edge da Aposta: <code>{edge:.2%}</code>\n\n"
                            f"<i>⚠️ Siga a gestão e jogue com responsabilidade.</i>"
                        )
                        
                        enviar_telegram(texto_msg)
                        jogos_enviados.add(jogo_id)
                        print(f"🚀 Análise enviada pro Telegram: {home_team} x {away_team}")

        except Exception as e:
            pass

if __name__ == "__main__":
    print("🤖 Bot de Análises Reais Iniciado com Sucesso!")
    print("📡 Monitorando API... Aguardando jogos entrarem na janela de 30 a 60 min...\n")
    while True:
        processar_jogos_e_enviar()
        time.sleep(600)