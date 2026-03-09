import requests
import time
import json
import os
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo

try:
    from services.result_checker import check_results
    from services.stats_analyzer import check_advanced_stats
    from services.auto_learning import is_league_profitable
except Exception as e:
    pass

# ==========================================
# 1. CONFIGURAÇÕES E CHAVES
# ==========================================
API_KEYS_ODDS =[
    "6a1c0078b3ed09b42fbacee8f07e7cc3",
    "4949c49070dd3eff2113bd1a07293165",
    "0ecb237829d0f800181538e1a4fa2494",
    "4790419cc795932ffaeb0152fa5818c8",
    "5ee1c6a8c611b6c3d6aff8043764555f"
]

API_KEYS_FOOTBALL =[
    "1cd3cb39658509019bdb1cdffff22c39",
    "f05d340d10ad108aae44ed8b674519f7",
    "f4ffd9cc04c586e9e1d62266db35bb0a"
]

TELEGRAM_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"
DB_FILE = "probum.db"

# Lista de casas de apostas para buscar Oportunidades (Soft Bookies)
SOFT_BOOKIES =["bet365", "betano", "1xbet", "draftkings", "williamhill", "unibet", "888sport", "betfair_ex_eu"]
SHARP_BOOKIE = "pinnacle"

LIGAS =[
    "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",              
    "soccer_germany_bundesliga", "soccer_france_ligue_one", "soccer_portugal_primeira_liga",
    "soccer_netherlands_eredivisie", "soccer_uefa_champs_league", "soccer_uefa_europa_league",
    "soccer_brazil_campeonato", "soccer_brazil_copa_do_brasil", "soccer_brazil_serie_b",
    "soccer_conmebol_copa_libertadores", "soccer_conmebol_copa_sudamericana",
    "soccer_argentina_primera_division", "soccer_mexico_ligamx", "soccer_usa_mls",
    "soccer_turkey_super_league", "soccer_belgium_first_div", "soccer_england_championship",
    "soccer_england_fa_cup", "soccer_uruguay_primera_division", 
    "basketball_nba", "basketball_euroleague", "basketball_ncaab"                     
]

jogos_enviados = set()
ultima_checagem_resultados = 0
chave_odds_atual = 0 
chave_football_atual = 0

# ==========================================
# 2. GERENCIADORES DE REQUISIÇÕES
# ==========================================
def fazer_requisicao_odds(url, parametros):
    global chave_odds_atual
    for tentativa in range(len(API_KEYS_ODDS)):
        chave_teste = API_KEYS_ODDS[chave_odds_atual]
        parametros["apiKey"] = chave_teste
        try:
            resposta = requests.get(url, params=parametros, timeout=15)
            if resposta.status_code == 200:
                restantes = resposta.headers.get('x-requests-remaining', '?')
                print(f"📡[Odds API - Chave {chave_odds_atual + 1}] OK! (Restam {restantes} reqs)")
                return resposta
            elif resposta.status_code in[401, 429]:
                print(f"❌[Odds API - Chave {chave_odds_atual + 1}] Esgotada! Pulando para a próxima...")
                chave_odds_atual = (chave_odds_atual + 1) % len(API_KEYS_ODDS)
            else:
                return resposta 
        except Exception as e:
            pass
    print("🚨 ATENÇÃO: TODAS as 5 chaves da The Odds API estouraram!")
    return None

def fazer_requisicao_football(url, parametros):
    global chave_football_atual
    for tentativa in range(len(API_KEYS_FOOTBALL)):
        chave_teste = API_KEYS_FOOTBALL[chave_football_atual]
        headers = {"x-apisports-key": chave_teste}
        try:
            resposta = requests.get(url, headers=headers, params=parametros, timeout=10)
            data = resposta.json()
            if resposta.status_code == 403 or ("errors" in data and data["errors"]):
                print(f"❌[Football API - Chave {chave_football_atual + 1}] Esgotada! Pulando...")
                chave_football_atual = (chave_football_atual + 1) % len(API_KEYS_FOOTBALL)
            else:
                return data
        except Exception as e:
            pass
    return None

def inicializar_banco():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operacoes_tipster (
            id_aposta TEXT PRIMARY KEY, esporte TEXT, jogo TEXT, liga TEXT, 
            mercado TEXT, selecao TEXT, odd REAL, prob REAL, ev REAL, stake REAL, 
            status TEXT DEFAULT 'PENDENTE', lucro REAL DEFAULT 0, data_hora TEXT
        )
    """)
    conn.commit()
    conn.close()

def salvar_aposta_sistema(bet_data):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO operacoes_tipster 
            (id_aposta, esporte, jogo, liga, mercado, selecao, odd, prob, ev, stake, status, data_hora)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            f"{bet_data['id']}_{bet_data['market_chosen']}", bet_data['sport_key'], 
            f"{bet_data['home']} x {bet_data['away']}", bet_data['league'], 
            bet_data['market_chosen'], bet_data.get('selecao', bet_data['market_chosen']), 
            bet_data['odd'], bet_data['prob'], bet_data['ev'], bet_data['stake_perc'], 
            "PENDENTE", bet_data['date']
        ))
        conn.commit()
        conn.close()
    except: pass

def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def buscar_id_time(nome_time):
    url = "https://v3.football.api-sports.io/teams"
    data = fazer_requisicao_football(url, {"search": nome_time})
    if data and data.get("results", 0) > 0: return data["response"][0]["team"]["id"]
    return None

def obter_historico_times(home_name, away_name):
    home_id = buscar_id_time(home_name)
    away_id = buscar_id_time(away_name)
    if not home_id or not away_id: return ""
    url_h2h = "https://v3.football.api-sports.io/fixtures/headtohead"
    data = fazer_requisicao_football(url_h2h, {"h2h": f"{home_id}-{away_id}", "last": 5})
    if data and data.get("results", 0) > 0:
        vitorias_home = sum(1 for m in data["response"] if (m["teams"]["home"]["winner"] and m["teams"]["home"]["id"] == home_id) or (m["teams"]["away"]["winner"] and m["teams"]["away"]["id"] == home_id))
        vitorias_away = sum(1 for m in data["response"] if (m["teams"]["home"]["winner"] and m["teams"]["home"]["id"] == away_id) or (m["teams"]["away"]["winner"] and m["teams"]["away"]["id"] == away_id))
        empates = data['results'] - vitorias_home - vitorias_away
        return f"\n📚 <b>HISTÓRICO H2H (Últimos {data['results']}):</b>\n✅ {home_name}: {vitorias_home} V\n✅ {away_name}: {vitorias_away} V\n➖ Empates: {empates}\n"
    return ""

# ==========================================
# 3. MOTOR DE ANÁLISE +EV E BUSCA MULTI-BOOKIES
# ==========================================
def calcular_prob_justa(outcomes):
    """Remove a margem de lucro (juice) da casa Sharp (Pinnacle)"""
    try:
        margem = sum(1 / item["price"] for item in outcomes if item["price"] > 0)
        probabilidades = {item["name"]: (1 / item["price"]) / margem for item in outcomes if item["price"] > 0}
        return probabilidades
    except:
        return {}

def processar_jogos_e_enviar():
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    print(f"\n🔄[ATUALIZAÇÃO - {agora_br.strftime('%H:%M:%S')}] Escaneando Valor Global...")
    
    for liga in LIGAS:
        time.sleep(1) # Previne erro 429 da API
        is_nba = "basketball" in liga
        
        # ATUALIZADO: Agora busca Empate Anula e Dupla Aposta
        mercados_alvo = "h2h,spreads,totals" if is_nba else "h2h,btts,totals,draw_no_bet,double_chance"
        
        casas_busca = f"{SHARP_BOOKIE}," + ",".join(SOFT_BOOKIES)
        parametros = {"regions": "eu,us", "markets": mercados_alvo, "bookmakers": casas_busca}
        url_odds = f"https://api.the-odds-api.com/v4/sports/{liga}/odds/"
        
        resposta = fazer_requisicao_odds(url_odds, parametros)
        if not resposta or resposta.status_code != 200: continue
            
        try:
            for evento in resposta.json():
                horario_br = datetime.fromisoformat(evento["commence_time"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Sao_Paulo"))
                minutos_faltando = (horario_br - agora_br).total_seconds() / 60
                
                if not (15 <= minutos_faltando <= 1440): continue # Jogos das próximas 24h

                bookmakers = evento.get("bookmakers", [])
                pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)
                if not pinnacle: continue # Se não tem a sharp, ignora análise

                home_team, away_team = evento["home_team"], evento["away_team"]
                oportunidades =[]
                
                # --- ITERAR SOBRE TODAS AS CASAS RECREATIVAS (SOFT BOOKIES) ---
                for soft_b in bookmakers:
                    if soft_b["key"] == SHARP_BOOKIE or soft_b["key"] not in SOFT_BOOKIES: continue
                    nome_casa = soft_b["title"]

                    # 1. MERCADO: MATCH ODDS (H2H)
                    pin_h2h = next((m for m in pinnacle.get("markets",[]) if m["key"] == "h2h"), None)
                    soft_h2h = next((m for m in soft_b.get("markets",[]) if m["key"] == "h2h"), None)
                    if pin_h2h and soft_h2h:
                        probs_justas = calcular_prob_justa(pin_h2h["outcomes"])
                        for s_outcome in soft_h2h["outcomes"]:
                            selecao = s_outcome["name"]
                            odd_oferecida = s_outcome["price"]
                            prob_real = probs_justas.get(selecao, 0)
                            
                            if prob_real > 0 and odd_oferecida > 1:
                                ev_real = (prob_real * odd_oferecida) - 1
                                if ev_real >= 0.015: # Mínimo de 1.5% EV
                                    oportunidades.append(("Vencedor (Moneyline)", selecao, odd_oferecida, prob_real, ev_real, nome_casa))

                    # 2. MERCADO: AMBAS MARCAM (BTTS)
                    pin_btts = next((m for m in pinnacle.get("markets",[]) if m["key"] == "btts"), None)
                    soft_btts = next((m for m in soft_b.get("markets",[]) if m["key"] == "btts"), None)
                    if pin_btts and soft_btts:
                        probs_justas = calcular_prob_justa(pin_btts["outcomes"])
                        for s_outcome in soft_btts["outcomes"]:
                            selecao = s_outcome["name"]
                            odd_oferecida = s_outcome["price"]
                            prob_real = probs_justas.get(selecao, 0)
                            
                            if prob_real > 0 and odd_oferecida > 1:
                                ev_real = (prob_real * odd_oferecida) - 1
                                if ev_real >= 0.015:
                                    selecao_br = "Sim" if selecao == "Yes" else "Não"
                                    oportunidades.append(("Ambas Marcam", selecao_br, odd_oferecida, prob_real, ev_real, nome_casa))

                    # 3. MERCADO: OVER/UNDER (TOTALS) - CORRIGIDO O CÁLCULO DE LINHAS
                    pin_tot = next((m for m in pinnacle.get("markets", []) if m["key"] == "totals"), None)
                    soft_tot = next((m for m in soft_b.get("markets",[]) if m["key"] == "totals"), None)
                    if pin_tot and soft_tot:
                        for s_outcome in soft_tot["outcomes"]:
                            selecao = f"{s_outcome['name']} {s_outcome.get('point', '')}"
                            odd_oferecida = s_outcome["price"]
                            ponto_atual = s_outcome.get("point")
                            
                            # Acha a odd correspondente na Pinnacle usando o nome (Over/Under) e a linha (point)
                            pin_match = next((p for p in pin_tot["outcomes"] if p["name"] == s_outcome["name"] and p.get("point") == ponto_atual), None)
                            
                            if pin_match:
                                # Pega o Over e o Under específicos daquela linha exata na Pinnacle para remover o Juice corretamente
                                par_pinnacle = [p for p in pin_tot["outcomes"] if p.get("point") == ponto_atual]
                                
                                try:
                                    # Calcula a margem justa apenas para esta linha de pontos (ex: apenas pro 2.5)
                                    margem_linha = sum(1 / item["price"] for item in par_pinnacle if item["price"] > 0)
                                    prob_real = (1 / pin_match["price"]) / margem_linha
                                    
                                    ev_real = (prob_real * odd_oferecida) - 1
                                    if ev_real >= 0.015:
                                        oportunidades.append(("Gols/Pontos (Totals)", selecao, odd_oferecida, prob_real, ev_real, nome_casa))
                                except ZeroDivisionError:
                                    continue

                    # 4. MERCADO: EMPATE ANULA APOSTA (DRAW NO BET) - NOVO
                    pin_dnb = next((m for m in pinnacle.get("markets",[]) if m["key"] == "draw_no_bet"), None)
                    soft_dnb = next((m for m in soft_b.get("markets",[]) if m["key"] == "draw_no_bet"), None)
                    if pin_dnb and soft_dnb:
                        probs_justas = calcular_prob_justa(pin_dnb["outcomes"])
                        for s_outcome in soft_dnb["outcomes"]:
                            selecao = s_outcome["name"]
                            odd_oferecida = s_outcome["price"]
                            prob_real = probs_justas.get(selecao, 0)
                            
                            if prob_real > 0 and odd_oferecida > 1:
                                ev_real = (prob_real * odd_oferecida) - 1
                                if ev_real >= 0.015:
                                    oportunidades.append(("Empate Anula (DNB)", selecao, odd_oferecida, prob_real, ev_real, nome_casa))

                    # 5. MERCADO: DUPLA APOSTA (DOUBLE CHANCE) - NOVO
                    pin_dc = next((m for m in pinnacle.get("markets", []) if m["key"] == "double_chance"), None)
                    soft_dc = next((m for m in soft_b.get("markets",[]) if m["key"] == "double_chance"), None)
                    if pin_dc and soft_dc:
                        probs_justas = calcular_prob_justa(pin_dc["outcomes"])
                        for s_outcome in soft_dc["outcomes"]:
                            selecao = s_outcome["name"]
                            odd_oferecida = s_outcome["price"]
                            prob_real = probs_justas.get(selecao, 0)
                            
                            if prob_real > 0 and odd_oferecida > 1:
                                ev_real = (prob_real * odd_oferecida) - 1
                                if ev_real >= 0.015:
                                    # Formata os nomes que a API manda (Ex: "Home/Draw" -> "Casa ou Empate")
                                    selecao_formatada = selecao.replace("/", " ou ")
                                    oportunidades.append(("Dupla Aposta (Chance Dupla)", selecao_formatada, odd_oferecida, prob_real, ev_real, nome_casa))

                if not oportunidades: continue
                
                # Pega a melhor oportunidade de todas as casas testadas para esse jogo
                melhor_op = max(oportunidades, key=lambda x: x[4]) 
                mercado_nome, selecao_nome, odd_bookie, prob_justa, ev_real, nome_bookie = melhor_op

                if ev_real >= 0.025: 
                    cabecalho = "💎 <b>APOSTA INSTITUCIONAL (SNIPER)</b> 💎"
                else: 
                    cabecalho = "🔥 <b>OPORTUNIDADE DE VALOR (MODERADA)</b> 🔥"
                
                # Kelly Criterion
                b_kelly = odd_bookie - 1
                q_kelly = 1 - prob_justa
                try: kelly_pct = max(0.5, min(((prob_justa - (q_kelly / b_kelly)) * 0.25) * 100, 3.0))
                except: kelly_pct = 1.0

                jogo_id = f"{evento['id']}_{mercado_nome}_{selecao_nome}"
                horas_f, min_f = int(minutos_faltando // 60), int(minutos_faltando % 60)
                tempo_str = f"{horas_f}h {min_f}min" if horas_f > 0 else f"{min_f} min"

                if jogo_id not in jogos_enviados:
                    emoji = "🏀" if is_nba else "⚽"
                    bloco_historico = f"\n{obter_historico_times(home_team, away_team)}" if not is_nba else ""
                    
                    texto_msg = (
                        f"{cabecalho}\n\n"
                        f"🏆 <b>Liga:</b> {evento['sport_title']}\n"
                        f"⏰ <b>Horário:</b> {horario_br.strftime('%H:%M')} (Faltam {tempo_str})\n"
                        f"{emoji} <b>Jogo:</b> {home_team} x {away_team}\n\n"
                        f"🎯 <b>Mercado:</b> {mercado_nome}\n"
                        f"👉 <b>Entrada:</b> {selecao_nome}\n"
                        f"🏛️ <b>Casa de Aposta:</b> {nome_bookie}\n"
                        f"📈 <b>Odd Atual:</b> {odd_bookie:.2f}\n\n"
                        f"💰 <b>Gestão Recomendada:</b> {kelly_pct:.1f}% da Banca\n"
                        f"📊 <b>Vantagem Matemática (+EV):</b> +{ev_real*100:.2f}%\n"
                        f"{bloco_historico}"
                    )
                    enviar_telegram(texto_msg)
                    jogos_enviados.add(jogo_id)

                    salvar_aposta_sistema({
                        "id": evento["id"], "sport_key": liga, "home": home_team, "away": away_team,
                        "league": evento['sport_title'], "market_chosen": mercado_nome, "selecao": selecao_nome,
                        "odd": round(odd_bookie, 2), "prob": prob_justa, "ev": ev_real, "stake_perc": round(kelly_pct, 2),
                        "date": horario_br.strftime('%d/%m/%Y')
                    })
                    print(f"🚀 ✅ TIP ENVIADA: {home_team} x {away_team} | {mercado_nome} | Casa: {nome_bookie} | EV: +{ev_real*100:.2f}%")

        except Exception as e: 
            print(f"⚠️ Erro no processamento: {e}")

# ==========================================
# 4. LOOP PRINCIPAL
# ==========================================
if __name__ == "__main__":
    inicializar_banco()
    print("🤖 Bot Institucional v2.0 Iniciado com Sucesso!")
    print("✅ Múltiplas Casas Ativadas (Bet365, Betano, 1xBet, etc.) | Busca de Mercado Expandida!")
    
    while True:
        processar_jogos_e_enviar()
        print("\n⏳ Aguardando 6 horas para a próxima varredura global...")
        time.sleep(21600)