import requests
import time
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from services.result_checker import check_results
from services.stats_analyzer import check_advanced_stats
from services.auto_learning import is_league_profitable  # 🧠 Módulo de aprendizado

# Configurações Reais
API_KEY_ODDS = "6a1c0078b3ed09b42fbacee8f07e7cc3"
TELEGRAM_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"

HISTORY_FILE = "bets_history.json"

# 🏆 LIGAS ATUALIZADAS
LIGAS =[
    "soccer_epl",                        
    "soccer_spain_la_liga",              
    "soccer_italy_serie_a",              
    "soccer_germany_bundesliga",         
    "soccer_brazil_campeonato",          
    "soccer_brazil_copa_do_brasil",      
    "soccer_conmebol_copa_libertadores", 
    "basketball_nba"                     
]

jogos_enviados = set()

def salvar_historico(bet_data):
    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                bets = json.load(f)
        else:
            bets =[]
    except:
        bets =[]

    bets.append(bet_data)

    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(bets, f, indent=2)

def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar pro Telegram: {e}")

def processar_jogos_e_enviar():
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    print(f"\n🔄[ATUALIZAÇÃO - {agora_br.strftime('%H:%M:%S')}] Buscando jogos (Todas as Seleções, Sharp Money e Kelly)...")

    for liga in LIGAS:
        is_nba = "basketball" in liga
        mercados_alvo = "h2h,totals,spreads" if is_nba else "h2h,totals,btts"
        
        url = f"https://api.the-odds-api.com/v4/sports/{liga}/odds/"
        parametros = {
            "apiKey": API_KEY_ODDS,
            "regions": "eu,uk,us",
            "markets": mercados_alvo,
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

                pinnacle = next((b for b in bookmakers if b["key"] == "pinnacle"), None)
                bet365 = next((b for b in bookmakers if b["key"] == "bet365"), bookmakers[0])

                mercados_b365 = bet365.get("markets",[])
                h2h_market = next((m for m in mercados_b365 if m["key"] == "h2h"), None)
                if not h2h_market: continue

                odds = h2h_market["outcomes"]
                home_team = evento["home_team"]
                away_team = evento["away_team"]
                liga_nome = evento['sport_title']

                odd_home = next((item["price"] for item in odds if item["name"] == home_team), 0)
                odd_away = next((item["price"] for item in odds if item["name"] == away_team), 0)
                odd_draw = next((item["price"] for item in odds if item["name"] == "Draw"), 0)

                if odd_home == 0 or odd_away == 0: continue

                # =========================================================
                # 🎯 NOVO 1: PROBABILIDADES E EV PARA TODOS OS MERCADOS
                # =========================================================
                pin_h, pin_a, pin_d = odd_home, odd_away, odd_draw # Fallback caso não tenha Pinnacle
                if pinnacle:
                    pin_h2h = next((m for m in pinnacle.get("markets",[]) if m["key"] == "h2h"), None)
                    if pin_h2h:
                        p_odds = pin_h2h["outcomes"]
                        pin_h = next((item["price"] for item in p_odds if item["name"] == home_team), odd_home)
                        pin_a = next((item["price"] for item in p_odds if item["name"] == away_team), odd_away)
                        pin_d = next((item["price"] for item in p_odds if item["name"] == "Draw"), odd_draw)

                # Remove a margem da Pinnacle para achar a % Exata de cada cenário
                margin = (1/pin_h) + (1/pin_a) + (1/pin_d if pin_d else 0)
                prob_h = (1/pin_h) / margin if pin_h else 0
                prob_a = (1/pin_a) / margin if pin_a else 0
                prob_d = (1/pin_d) / margin if pin_d else 0

                # Calcula o EV para Casa, Visitante e Empate na Bet365
                ev_h = (prob_h * odd_home) - 1 if odd_home else -1
                ev_a = (prob_a * odd_away) - 1 if odd_away else -1
                ev_d = (prob_d * odd_draw) - 1 if odd_draw else -1

                # Cria uma lista de oportunidades válidas
                oportunidades =[]
                if ev_h > 0: oportunidades.append(("Vitória Casa", home_team, odd_home, prob_h, ev_h, pin_h))
                if ev_a > 0: oportunidades.append(("Vitória Visitante", away_team, odd_away, prob_a, ev_a, pin_a))
                if not is_nba and ev_d > 0: oportunidades.append(("Empate", "Empate", odd_draw, prob_d, ev_d, pin_d))

                if not oportunidades: continue

                # Seleciona automaticamente a MAIOR OPORTUNIDADE MATEMÁTICA do jogo
                melhor_op = max(oportunidades, key=lambda x: x[4])
                selecao_tipo, selecao_nome, odd_b365, prob_justa, ev_real, odd_pin = melhor_op

                # Só avança se o EV da melhor opção for maior que 2%
                if ev_real < 0.02: continue

                # =========================================================
                # 📈 NOVO 3: RASTREADOR DE SHARP MONEY (DROPPING ODDS)
                # =========================================================
                sharp_money_alert = ""
                # Se a Bet365 está pagando pelo menos 4% a mais que a Pinnacle, a odd da B365 está desatualizada!
                if odd_b365 > (odd_pin * 1.04):
                    sharp_money_alert = (
                        f"🚨 <b>SHARP MONEY (ODD DESATUALIZADA)</b> 🚨\n"
                        f"A Pinnacle já derrubou essa odd para <b>{odd_pin}</b> devido ao alto volume de dinheiro "
                        f"profissional. A Bet365 está atrasada pagando <b>{odd_b365}</b>. Aposte rápido!\n\n"
                    )

                # =========================================================
                # 💰 NOVO 4: CRITÉRIO DE KELLY (GESTÃO DE BANCA MATEMÁTICA)
                # =========================================================
                b = odd_b365 - 1
                q = 1 - prob_justa
                # Fórmula Full Kelly
                kelly_full = prob_justa - (q / b)
                # Usamos Quarter Kelly (25%) para segurança do caixa
                stake_kelly_pct = (kelly_full * 0.25) * 100 
                # Limitamos a no mínimo 0.5% e no máximo 3.0% da banca para evitar loucuras
                stake_kelly_pct = max(0.5, min(stake_kelly_pct, 3.0))

                # =========================================================
                # SUGESTÕES SECUNDÁRIAS (GOLS PARA FUT, HANDICAP/PONTOS PARA NBA)
                # =========================================================
                sugestao_extra = ""
                if is_nba:
                    spread_point, spread_odd = "", 0
                    spreads_market = next((m for m in mercados_b365 if m["key"] == "spreads"), None)
                    if spreads_market:
                        for out in spreads_market["outcomes"]:
                            if out["name"] == home_team:
                                spread_point = out.get("point", "")
                                spread_odd = out["price"]
                                break
                    
                    total_point, total_odd = "", 0
                    totals_market = next((m for m in mercados_b365 if m["key"] == "totals"), None)
                    if totals_market:
                        for out in totals_market["outcomes"]:
                            if out["name"] == "Over":
                                total_point = out.get("point", "")
                                total_odd = out["price"]
                                break
                    
                    if spread_odd > 0: sugestao_extra += f"🏀 <b>Handicap Casa:</b> {home_team} {spread_point} (Odd {spread_odd})\n"
                    if total_odd > 0: sugestao_extra += f"🔥 <b>Pontos Totais:</b> Mais de {total_point} pontos (Odd {total_odd})\n"
                else:
                    over25_odd, btts_odd = 0, 0
                    totals_market = next((m for m in mercados_b365 if m["key"] == "totals"), None)
                    if totals_market:
                        for out in totals_market["outcomes"]:
                            if out["name"] == "Over" and float(out.get("point", 0)) == 2.5:
                                over25_odd = out["price"]
                    
                    btts_market = next((m for m in mercados_b365 if m["key"] == "btts"), None)
                    if btts_market:
                        for out in btts_market["outcomes"]:
                            if out["name"] == "Yes": btts_odd = out["price"]

                    if over25_odd > 0 and over25_odd <= 1.75:
                        sugestao_extra = f"⚽ <b>Opção de Gols:</b> Over 2.5 (Odd {over25_odd})\n"
                    elif btts_odd > 0 and btts_odd <= 1.80:
                        sugestao_extra = f"⚽ <b>Opção de Gols:</b> Ambas Marcam - Sim (Odd {btts_odd})\n"

                # Filtros
                if not is_league_profitable(liga_nome): continue 
                if odd_b365 < 1.25 or odd_b365 > 3.50: continue  # Margem ampliada para pegar Visitantes e Empates
                
                if not is_nba:
                    aprovado = check_advanced_stats(home_team, away_team)
                    if not aprovado: continue

                emoji = "🏀" if is_nba else "⚽"

                jogo_id = evento["id"]
                minutos_faltando = (horario_br - agora_br).total_seconds() / 60

                if 30 <= minutos_faltando <= 60:
                    if jogo_id not in jogos_enviados:

                        texto_msg = (
                            f"💎 <b>APOSTA PREMIUM DETECTADA</b> 💎\n\n"
                            f"{sharp_money_alert}"
                            f"🏆 <b>Liga:</b> {liga_nome}\n"
                            f"⏰ <b>Horário:</b> {horario_br.strftime('%H:%M')} (Faltam {int(minutos_faltando)} min)\n"
                            f"{emoji} <b>Jogo:</b> {home_team} x {away_team}\n\n"
                            f"🎯 <b>MERCADO DE MAIOR VALOR (+EV):</b>\n"
                            f"👉 <b>{selecao_tipo}: {selecao_nome}</b>\n"
                            f"📈 <b>Odd Atual (Bet365):</b> {odd_b365}\n"
                        )
                        
                        if sugestao_extra: texto_msg += f"\n{sugestao_extra}"

                        texto_msg += (
                            f"\n💰 <b>Gestão de Banca (Critério de Kelly):</b>\n"
                            f"Risco Calculado: Usar exatos <b>{stake_kelly_pct:.2f}%</b> da sua Banca.\n\n"
                            f"📊 <b>Inteligência Matemática:</b>\n"
                            f"✅ <b>Margem de Erro Casa/Pinnacle:</b> Vantagem de +{ev_real*100:.2f}%\n"
                            f"✅ <b>Probabilidade Real (Sem Vig):</b> {prob_justa*100:.1f}%\n\n"
                            f"<i>⚠️ Jogue com a gestão indicada acima.</i>"
                        )

                        enviar_telegram(texto_msg)

                        salvar_historico({
                            "id": jogo_id,
                            "sport_key": liga,
                            "home": home_team,
                            "away": away_team,
                            "league": liga_nome,
                            "market_chosen": selecao_tipo,
                            "odd": odd_b365,
                            "prob": prob_justa, 
                            "ev": ev_real,           
                            "stake_perc": round(stake_kelly_pct, 2),
                            "checked": False,
                            "result": None,
                            "profit": 0,
                            "date": horario_br.strftime('%d/%m/%Y')
                        })

                        jogos_enviados.add(jogo_id)
                        print(f"🚀 Análise enviada: {selecao_nome} na odd {odd_b365} | EV: +{ev_real*100:.2f}%")

        except Exception as e:
            pass

if __name__ == "__main__":
    print("🤖 Bot Profissional Iniciado!")
    print("✅ Módulos Ativos: Análise 360º (Visitantes/Empate) | Rastreador Sharp Money | Critério Kelly")
    while True:
        processar_jogos_e_enviar()
        try:
            check_results()
        except:
            pass
        time.sleep(600)