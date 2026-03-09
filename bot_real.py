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
# 1. RODÍZIO DA "THE ODDS API" (Busca Valor/EV)
# Total de 5 Chaves = 2.500 requisições/mês
# ==========================================
API_KEYS_ODDS =[
    "6a1c0078b3ed09b42fbacee8f07e7cc3",  # Chave 1 (Original)
    "4949c49070dd3eff2113bd1a07293165",  # Chave 2
    "0ecb237829d0f800181538e1a4fa2494",  # Chave 3
    "4790419cc795932ffaeb0152fa5818c8",  # Chave 4
    "5ee1c6a8c611b6c3d6aff8043764555f"   # Chave 5
]

# ==========================================
# 2. RODÍZIO DA "API-FOOTBALL" (Busca Histórico H2H)
# ==========================================
API_KEYS_FOOTBALL =[
    "1cd3cb39658509019bdb1cdffff22c39",
    "f05d340d10ad108aae44ed8b674519f7",
    "f4ffd9cc04c586e9e1d62266db35bb0a"
]

TELEGRAM_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"
HISTORY_FILE = "bets_history.json"
DB_FILE = "probum.db"

LIGAS =[
    "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",              
    "soccer_germany_bundesliga", "soccer_france_ligue_one", "soccer_portugal_primeira_liga",
    "soccer_netherlands_eredivisie", "soccer_uefa_champs_league", "soccer_uefa_europa_league",
    "soccer_brazil_campeonato", "soccer_brazil_copa_do_brasil", "soccer_brazil_serie_b",
    "soccer_conmebol_copa_libertadores", "soccer_conmebol_copa_sudamericana",
    "soccer_argentina_primera_division", "soccer_mexico_ligamx", "soccer_usa_mls",
    "soccer_turkey_super_league", "soccer_belgium_first_div", "soccer_england_championship",
    "soccer_england_fa_cup", 
    "soccer_uruguay_primera_division", 
    "basketball_nba", "basketball_euroleague", "basketball_ncaab"                     
]

jogos_enviados = set()
ultima_checagem_resultados = 0
chave_odds_atual = 0 
chave_football_atual = 0

# ==========================================
# GERENCIADORES DE REQUISIÇÕES (PLANO B DUPLO)
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
                print(f"📡[Odds API - Chave {chave_odds_atual + 1}] OK! (Restam {restantes} reqs nesta chave)")
                return resposta
            elif resposta.status_code in[401, 429]:
                print(f"❌[Odds API - Chave {chave_odds_atual + 1}] Esgotada! Pulando para a próxima...")
                chave_odds_atual = (chave_odds_atual + 1) % len(API_KEYS_ODDS)
            else:
                return resposta 
        except Exception as e:
            return None
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
                print(f"❌[Football API - Chave {chave_football_atual + 1}] Esgotada! Pulando para a próxima...")
                chave_football_atual = (chave_football_atual + 1) % len(API_KEYS_FOOTBALL)
            else:
                return data
        except Exception as e:
            return None
    print("🚨 ATENÇÃO: Todas as chaves da API-Football estouraram (100 reqs/dia)!")
    return None

def inicializar_banco():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operacoes_tipster (
            id_aposta TEXT PRIMARY KEY,
            esporte TEXT,
            jogo TEXT,
            liga TEXT,
            mercado TEXT,
            selecao TEXT,
            odd REAL,
            prob REAL,
            ev REAL,
            stake REAL,
            status TEXT DEFAULT 'PENDENTE',
            lucro REAL DEFAULT 0,
            data_hora TEXT
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
    if data and data.get("results", 0) > 0:
        return data["response"][0]["team"]["id"]
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
        return f"\n📚 <b>HISTÓRICO H2H (Últimos {data['results']}):</b>\n✅ {home_name}: {vitorias_home} Vitórias\n✅ {away_name}: {vitorias_away} Vitórias\n➖ Empates: {empates}\n"
    return ""

def verificar_resultados_automatico():
    global ultima_checagem_resultados
    agora = time.time()
    if agora - ultima_checagem_resultados < 3600: return 
    ultima_checagem_resultados = agora
    
    print("\n🔎 Verificando Greens/Reds no Banco de Dados...")
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT id_aposta, esporte, jogo, mercado, selecao, odd, stake FROM operacoes_tipster WHERE status = 'PENDENTE'")
        pendentes = cursor.fetchall()
        
        if not pendentes: 
            conn.close(); return

        esportes_pendentes = set([p[1] for p in pendentes])
        
        for esporte in esportes_pendentes:
            url_scores = f"https://api.the-odds-api.com/v4/sports/{esporte}/scores/"
            resp = fazer_requisicao_odds(url_scores, {"daysFrom": 2})
            if not resp or resp.status_code != 200: continue
            
            scores_data = resp.json()

            for aposta in pendentes:
                id_ap, esp, jogo_nome, mercado, selecao, odd, stake = aposta
                if esp != esporte or "Player" in mercado or "Jogador" in mercado: continue
                
                times = jogo_nome.split(" x ")
                if len(times) != 2: continue
                home_t, away_t = times[0], times[1]

                game = next((g for g in scores_data if g["home_team"] == home_t and g["away_team"] == away_t), None)
                if not game or not game.get("completed") or not game.get("scores"): continue
                
                scores = game.get("scores")
                home_score = int(next((s["score"] for s in scores if s["name"] == home_t), 0))
                away_score = int(next((s["score"] for s in scores if s["name"] == away_t), 0))
                
                res_final, lucro = "RED", -stake
                
                if "Vitória Casa" in mercado and home_score > away_score: res_final = "GREEN"
                elif "Vitória Visitante" in mercado and away_score > home_score: res_final = "GREEN"
                elif "Ambas Marcam" in mercado:
                    if "Sim" in selecao and home_score > 0 and away_score > 0: res_final = "GREEN"
                    elif "Não" in selecao and (home_score == 0 or away_score == 0): res_final = "GREEN"
                elif "Empate Anula" in mercado:
                    if "Casa" in mercado and home_score > away_score: res_final = "GREEN"
                    elif "Visit" in mercado and away_score > home_score: res_final = "GREEN"
                    elif home_score == away_score: res_final = "REEMBOLSO"
                elif "Asiático" in mercado or "Totals" in mercado:
                    soma = home_score + away_score
                    linha = float(selecao.split()[-1])
                    if "Over" in selecao and soma > linha: res_final = "GREEN"
                    elif "Under" in selecao and soma < linha: res_final = "GREEN"

                if res_final == "GREEN": lucro = stake * (odd - 1)
                elif res_final == "REEMBOLSO": lucro = 0

                cursor.execute("UPDATE operacoes_tipster SET status = ?, lucro = ? WHERE id_aposta = ?", (res_final, lucro, id_ap))
                conn.commit()

                if res_final == "GREEN": enviar_telegram(f"✅ <b>GREEN! LUCRO NO BOLSO!</b> 💰\n⚽ {jogo_nome} ({home_score}x{away_score})\n🎯 Bateu: {mercado} - {selecao}\n📈 +{lucro:.2f} Unidades.")
                elif res_final == "REEMBOLSO": enviar_telegram(f"🔄 <b>REEMBOLSADA (VOID)</b>\n⚽ {jogo_nome} ({home_score}x{away_score})\n🎯 Dinheiro de volta!")
                else: enviar_telegram(f"❌ <b>RED</b>\n⚽ {jogo_nome} ({home_score}x{away_score})\n🎯 {mercado} não bateu.")
                    
        conn.close()
    except Exception as e: print(f"⚠️ Erro ao verificar resultados: {e}")

def processar_jogos_e_enviar():
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    print(f"\n🔄[ATUALIZAÇÃO - {agora_br.strftime('%H:%M:%S')}] Escaneando Valor (Mínimo EV: 1.0%)...")
    
    for liga in LIGAS:
        is_nba = "basketball" in liga
        mercados_alvo = "h2h,spreads" if is_nba else "h2h,btts"
        
        # Filtro de economia extrema: Apenas europa (pega Pinnacle/Bet365)
        parametros = {"regions": "eu", "markets": mercados_alvo, "bookmakers": "bet365,pinnacle"}
        url_odds = f"https://api.the-odds-api.com/v4/sports/{liga}/odds/"
        
        resposta = fazer_requisicao_odds(url_odds, parametros)
        
        if not resposta or resposta.status_code != 200: 
            if resposta and resposta.status_code == 429:
                return 
            continue
            
        try:
            for evento in resposta.json():
                horario_br = datetime.fromisoformat(evento["commence_time"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Sao_Paulo"))
                minutos_faltando = (horario_br - agora_br).total_seconds() / 60
                
                # Foca em jogos das próximas 12h
                if not (15 <= minutos_faltando <= 720): continue

                bookmakers = evento.get("bookmakers",[])
                pinnacle = next((b for b in bookmakers if b["key"] == "pinnacle"), None)
                bet365 = next((b for b in bookmakers if b["key"] == "bet365"), next((b for b in bookmakers if b["key"] == "draftkings"), None))
                
                home_team, away_team = evento["home_team"], evento["away_team"]
                jogo_str = f"{home_team} x {away_team}"

                if not pinnacle or not bet365: continue

                oportunidades =[]
                
                # 1. AMBAS MARCAM (BTTS)
                pin_btts = next((m for m in pinnacle.get("markets", []) if m["key"] == "btts"), None)
                b365_btts = next((m for m in bet365.get("markets",[]) if m["key"] == "btts"), None)
                if pin_btts and b365_btts and len(pin_btts["outcomes"]) == 2:
                    p_y, p_n = pin_btts["outcomes"][0]["price"], pin_btts["outcomes"][1]["price"]
                    b_y = next((i["price"] for i in b365_btts["outcomes"] if i["name"] == pin_btts["outcomes"][0]["name"]), 0)
                    b_n = next((i["price"] for i in b365_btts["outcomes"] if i["name"] == pin_btts["outcomes"][1]["name"]), 0)
                    if p_y > 0 and p_n > 0:
                        margin = (1/p_y) + (1/p_n)
                        prob_y, prob_n = (1/p_y) / margin, (1/p_n) / margin
                        ev_y, ev_n = (prob_y * b_y) - 1 if b_y else -1, (prob_n * b_n) - 1 if b_n else -1
                        
                        if ev_y >= 0.01: oportunidades.append(("Ambas Marcam", "Sim", b_y, prob_y, ev_y))
                        if ev_n >= 0.01: oportunidades.append(("Ambas Marcam", "Não", b_n, prob_n, ev_n))

                # 2. H2H E EMPATE ANULA (DNB)
                pin_h2h = next((m for m in pinnacle.get("markets",[]) if m["key"] == "h2h"), None)
                b365_h2h = next((m for m in bet365.get("markets",[]) if m["key"] == "h2h"), None)
                if pin_h2h and b365_h2h and len(pin_h2h["outcomes"]) >= 2:
                    pin_h = next((i["price"] for i in pin_h2h["outcomes"] if i["name"] == home_team), 0)
                    pin_a = next((i["price"] for i in pin_h2h["outcomes"] if i["name"] == away_team), 0)
                    pin_d = next((i["price"] for i in pin_h2h["outcomes"] if i["name"] == "Draw"), 0)
                    b365_h = next((i["price"] for i in b365_h2h["outcomes"] if i["name"] == home_team), 0)
                    b365_a = next((i["price"] for i in b365_h2h["outcomes"] if i["name"] == away_team), 0)
                    b365_d = next((i["price"] for i in b365_h2h["outcomes"] if i["name"] == "Draw"), 0)

                    if pin_h > 0 and pin_a > 0:
                        margin = (1/pin_h) + (1/pin_a) + (1/pin_d if pin_d else 0)
                        prob_h, prob_a = (1/pin_h) / margin, (1/pin_a) / margin
                        ev_h, ev_a = (prob_h * b365_h) - 1 if b365_h else -1, (prob_a * b365_a) - 1 if b365_a else -1

                        if ev_h >= 0.01: oportunidades.append(("Vitória Casa", home_team, b365_h, prob_h, ev_h))
                        if ev_a >= 0.01: oportunidades.append(("Vitória Visitante", away_team, b365_a, prob_a, ev_a))

                        if not is_nba and b365_d > 1:
                            dnb_h, dnb_a = (b365_h * (b365_d - 1)) / b365_d, (b365_a * (b365_d - 1)) / b365_d
                            prob_dnb_h = prob_h / (prob_h + prob_a) if (prob_h + prob_a) > 0 else 0
                            ev_dnb_h = (prob_dnb_h * dnb_h) - 1
                            if ev_dnb_h >= 0.01: oportunidades.append(("Empate Anula", f"Casa ({home_team})", dnb_h, prob_dnb_h, ev_dnb_h))

                if not oportunidades: continue
                
                melhor_op = max(oportunidades, key=lambda x: x[4]) 
                mercado_nome, selecao_nome, odd_b365, prob_justa, ev_real = melhor_op

                if ev_real >= 0.02: 
                    cabecalho = "💎 <b>APOSTA INSTITUCIONAL (SNIPER)</b> 💎"
                    b_kelly = odd_b365 - 1
                    q_kelly = 1 - prob_justa
                    kelly_pct = max(1.0, min(((prob_justa - (q_kelly / b_kelly)) * 0.25) * 100, 3.0)) 
                elif ev_real >= 0.01: 
                    cabecalho = "🔥 <b>OPORTUNIDADE DE VALOR (MODERADA)</b> 🔥"
                    kelly_pct = 0.5 

                jogo_id = f"{evento['id']}_{mercado_nome}"
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
                        f"🎯 <b>MERCADO (+EV):</b>\n"
                        f"👉 <b>{mercado_nome}: {selecao_nome}</b>\n"
                        f"📈 <b>Odd Atual:</b> {odd_b365:.2f}\n\n"
                        f"💰 <b>Gestão Recomendada:</b> {kelly_pct:.1f}% da Banca\n"
                        f"📊 <b>Vantagem Matemática:</b> +{ev_real*100:.2f}%\n"
                        f"{bloco_historico}"
                    )
                    enviar_telegram(texto_msg)
                    jogos_enviados.add(jogo_id)

                    salvar_aposta_sistema({
                        "id": evento["id"], "sport_key": liga, "home": home_team, "away": away_team,
                        "league": evento['sport_title'], "market_chosen": mercado_nome, "selecao": selecao_nome,
                        "odd": round(odd_b365, 2), "prob": prob_justa, "ev": ev_real, "stake_perc": round(kelly_pct, 2),
                        "date": horario_br.strftime('%d/%m/%Y')
                    })
                    print(f"🚀 ✅ TIP ENVIADA: {jogo_str} | Mercado: {mercado_nome} | EV: +{ev_real*100:.2f}%")

        except Exception as e: 
            print(f"⚠️ Erro de loop na liga: {e}")

if __name__ == "__main__":
    inicializar_banco()
    print("🤖 Bot Institucional Iniciado com Sucesso!")
    print("✅ Rodízio Total (5 Chaves Odds / 3 Chaves Football) | Cálculo p/ durar 30 Dias!")
    while True:
        processar_jogos_e_enviar()
        verificar_resultados_automatico()
        
        # ⚠️ MATEMÁTICA DO MÊS INTEIRO ⚠️
        # 43200 segundos = 12 horas. 
        # Ele vai rodar só 2 vezes ao dia (Pegando os jogos de Manhã e de Noite). 
        # Com isso, suas 5 chaves não estouram antes do mês virar!
        print("\n⏳ Aguardando 12 horas (Modo Matemática Inteligente) para a próxima varredura global...")
        time.sleep(43200)