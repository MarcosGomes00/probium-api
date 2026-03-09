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
except Exception:
    pass

# ==========================================
# CONFIGURAÇÕES REAIS E INTEGRAÇÃO DB
# ==========================================
API_KEY_ODDS = "6a1c0078b3ed09b42fbacee8f07e7cc3"
API_FOOTBALL_KEY = "1cd3cb39658509019bdb1cdffff22c39" 
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
    "basketball_nba", "basketball_euroleague", "basketball_ncaab"                     
]

jogos_enviados = set()
ultima_checagem_resultados = 0

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

    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f: bets = json.load(f)
        else: bets =[]
        bets.append(bet_data)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f: json.dump(bets, f, indent=2)
    except: pass

def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def buscar_id_time(nome_time):
    url = "https://v3.football.api-sports.io/teams"
    headers = {"x-apisports-key": API_FOOTBALL_KEY}
    try:
        data = requests.get(url, headers=headers, params={"search": nome_time}, timeout=10).json()
        if data.get("results", 0) > 0: return data["response"][0]["team"]["id"]
    except: pass
    return None

def obter_historico_times(home_name, away_name):
    home_id = buscar_id_time(home_name)
    away_id = buscar_id_time(away_name)
    if not home_id or not away_id: return ""

    try:
        url_h2h = "https://v3.football.api-sports.io/fixtures/headtohead"
        data = requests.get(url_h2h, headers={"x-apisports-key": API_FOOTBALL_KEY}, params={"h2h": f"{home_id}-{away_id}", "last": 5}, timeout=10).json()
        
        if data.get("results", 0) > 0:
            vitorias_home = sum(1 for m in data["response"] if (m["teams"]["home"]["winner"] and m["teams"]["home"]["id"] == home_id) or (m["teams"]["away"]["winner"] and m["teams"]["away"]["id"] == home_id))
            vitorias_away = sum(1 for m in data["response"] if (m["teams"]["home"]["winner"] and m["teams"]["home"]["id"] == away_id) or (m["teams"]["away"]["winner"] and m["teams"]["away"]["id"] == away_id))
            empates = data['results'] - vitorias_home - vitorias_away
            
            return f"\n📚 <b>HISTÓRICO H2H (Últimos {data['results']}):</b>\n✅ {home_name}: {vitorias_home} Vitórias\n✅ {away_name}: {vitorias_away} Vitórias\n➖ Empates: {empates}\n"
    except: pass
    return ""

def buscar_valor_linhas_asiaticas(pinnacle, bet365, nome_mercado, jogo_str):
    oportunidades =[]
    pin_market = next((m for m in pinnacle.get("markets",[]) if m["key"] == nome_mercado), None)
    b365_market = next((m for m in bet365.get("markets", []) if m["key"] == nome_mercado), None)

    if not pin_market or not b365_market: return oportunidades

    grupos_pin = {}
    for out in pin_market["outcomes"]:
        desc, pt = out.get("description", "Jogo"), out.get("point", "")
        if not pt: continue
        chave = f"{desc}_{pt}"
        if chave not in grupos_pin: grupos_pin[chave] =[]
        grupos_pin[chave].append(out)

    for chave, outs in grupos_pin.items():
        if len(outs) == 2:
            margin = (1/outs[0]["price"]) + (1/outs[1]["price"])
            for p_out in outs:
                prob = (1/p_out["price"]) / margin
                for b_out in b365_market["outcomes"]:
                    if b_out["name"] == p_out["name"] and b_out.get("point") == p_out.get("point") and b_out.get("description", "Jogo") == p_out.get("description", "Jogo"):
                        ev = (prob * b_out["price"]) - 1
                        
                        # RADAR: Avisa na tela se achou algo bom, mas exige 2% para mandar pro Telegram!
                        if 0.01 <= ev < 0.02: 
                            print(f"   [👀 RADAR] {jogo_str} | {nome_mercado} | +EV: {ev*100:.2f}% (Falta pouco pra bater a meta de 2%)")
                            
                        # RETORNAMOS PARA A EXIGÊNCIA MÁXIMA INSTITUCIONAL DE 2%
                        if ev >= 0.02: 
                            mercado_pt = nome_mercado.replace("_", " ").title()
                            selecao = f"{b_out.get('description', 'Jogo')} - {b_out['name']} {b_out['point']}"
                            oportunidades.append((mercado_pt, selecao, b_out["price"], prob, ev))
    return oportunidades

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
            resp = requests.get(f"https://api.the-odds-api.com/v4/sports/{esporte}/scores/", params={"apiKey": API_KEY_ODDS, "daysFrom": 2}, timeout=15)
            if resp.status_code != 200: continue
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
    except: pass

def processar_jogos_e_enviar():
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    print(f"\n🔄[ATUALIZAÇÃO - {agora_br.strftime('%H:%M:%S')}] Escaneando Valor (+EV >= 2%) nas próximas 12 horas...")

    bilhetes_potenciais =[]

    for liga in LIGAS:
        is_nba = "basketball" in liga
        mercados_alvo = "h2h,totals,spreads,player_points" if is_nba else "h2h,totals,spreads,btts,player_shots_on_target"
        
        parametros = {"apiKey": API_KEY_ODDS, "regions": "eu,uk,us", "markets": mercados_alvo, "bookmakers": "bet365,pinnacle"}

        try:
            resposta = requests.get(f"https://api.the-odds-api.com/v4/sports/{liga}/odds/", params=parametros, timeout=15)
            if resposta.status_code != 200: continue
            
            for evento in resposta.json():
                horario_br = datetime.fromisoformat(evento["commence_time"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Sao_Paulo"))
                minutos_faltando = (horario_br - agora_br).total_seconds() / 60
                
                # ⏳ A MÁGICA ESTÁ AQUI: Visão de 12 horas (720 minutos), mas exigência de Qualidade Alta!
                if not (15 <= minutos_faltando <= 720): continue

                bookmakers = evento.get("bookmakers",[])
                pinnacle = next((b for b in bookmakers if b["key"] == "pinnacle"), None)
                bet365 = next((b for b in bookmakers if b["key"] == "bet365"), next((b for b in bookmakers if b["key"] == "draftkings"), None))
                
                if not pinnacle or not bet365: continue

                home_team, away_team = evento["home_team"], evento["away_team"]
                jogo_str = f"{home_team} x {away_team}"
                oportunidades =[]

                # 1. MERCADOS ASIÁTICOS E TOTAIS
                oportunidades.extend(buscar_valor_linhas_asiaticas(pinnacle, bet365, "spreads", jogo_str))
                oportunidades.extend(buscar_valor_linhas_asiaticas(pinnacle, bet365, "totals", jogo_str))
                if is_nba: oportunidades.extend(buscar_valor_linhas_asiaticas(pinnacle, bet365, "player_points", jogo_str))
                else: oportunidades.extend(buscar_valor_linhas_asiaticas(pinnacle, bet365, "player_shots_on_target", jogo_str))

                # 2. AMBAS MARCAM (BTTS)
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
                        
                        if 0.01 <= ev_y < 0.02: print(f"   [👀 RADAR] {jogo_str} | BTTS Sim | +EV: {ev_y*100:.2f}%")
                        if ev_y >= 0.02: oportunidades.append(("Ambas Marcam", "Sim", b_y, prob_y, ev_y))
                        if ev_n >= 0.02: oportunidades.append(("Ambas Marcam", "Não", b_n, prob_n, ev_n))

                # 3. H2H E EMPATE ANULA (DNB)
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

                        if 0.01 <= ev_h < 0.02: print(f"   [👀 RADAR] {jogo_str} | Vence Casa | +EV: {ev_h*100:.2f}%")

                        if ev_h >= 0.02: oportunidades.append(("Vitória Casa", home_team, b365_h, prob_h, ev_h))
                        if ev_a >= 0.02: oportunidades.append(("Vitória Visitante", away_team, b365_a, prob_a, ev_a))

                        if not is_nba and b365_d > 1:
                            dnb_h, dnb_a = (b365_h * (b365_d - 1)) / b365_d, (b365_a * (b365_d - 1)) / b365_d
                            prob_dnb_h = prob_h / (prob_h + prob_a) if (prob_h + prob_a) > 0 else 0
                            ev_dnb_h = (prob_dnb_h * dnb_h) - 1
                            if ev_dnb_h >= 0.02: oportunidades.append(("Empate Anula", f"Casa ({home_team})", dnb_h, prob_dnb_h, ev_dnb_h))

                if not oportunidades: continue
                melhor_op = max(oportunidades, key=lambda x: x[4]) 
                mercado_nome, selecao_nome, odd_b365, prob_justa, ev_real = melhor_op

                b_kelly = odd_b365 - 1
                q_kelly = 1 - prob_justa
                kelly_pct = max(0.5, min(((prob_justa - (q_kelly / b_kelly)) * 0.25) * 100, 3.0))

                jogo_id = f"{evento['id']}_{mercado_nome}"
                horas_f, min_f = int(minutos_faltando // 60), int(minutos_faltando % 60)
                tempo_str = f"{horas_f}h {min_f}min" if horas_f > 0 else f"{min_f} min"

                if 1.30 <= odd_b365 <= 1.60:
                    bilhetes_potenciais.append({
                        "id": jogo_id, "home": home_team, "away": away_team, "liga": evento['sport_title'],
                        "horario": horario_br.strftime('%H:%M'), "mercado": mercado_nome, "selecao": selecao_nome,
                        "odd": odd_b365, "ev": ev_real
                    })

                if jogo_id not in jogos_enviados:
                    emoji = "🏀" if is_nba else "⚽"
                    bloco_historico = f"\n{obter_historico_times(home_team, away_team)}" if not is_nba else ""
                    
                    texto_msg = (
                        f"💎 <b>APOSTA PREMIUM DETECTADA</b> 💎\n\n"
                        f"🏆 <b>Liga:</b> {evento['sport_title']}\n"
                        f"⏰ <b>Horário:</b> {horario_br.strftime('%H:%M')} (Faltam {tempo_str})\n"
                        f"{emoji} <b>Jogo:</b> {home_team} x {away_team}\n\n"
                        f"🎯 <b>MERCADO (+EV):</b>\n"
                        f"👉 <b>{mercado_nome}: {selecao_nome}</b>\n"
                        f"📈 <b>Odd Atual:</b> {odd_b365:.2f}\n\n"
                        f"💰 <b>Gestão Inteligente:</b> {kelly_pct:.1f}% da Banca\n"
                        f"📊 <b>Vantagem Matemática:</b> +{ev_real*100:.1f}%\n"
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
                    print(f"🚀 Tip enviada: {mercado_nome} - {selecao_nome} | EV: +{ev_real*100:.2f}%")

        except Exception: pass

    if len(bilhetes_potenciais) >= 2:
        bilhetes_potenciais.sort(key=lambda x: x['ev'], reverse=True)
        top_2 = bilhetes_potenciais[:2]
        id_multipla = f"MULT_{top_2[0]['id']}_{top_2[1]['id']}"
        
        if id_multipla not in jogos_enviados:
            odd_total = top_2[0]['odd'] * top_2[1]['odd']
            msg_multipla = (
                f"🎫 <b>BILHETE DUPLO DA INTELIGÊNCIA ARTIFICIAL</b> 🎫\n"
                f"<i>Análise cruzada de alta segurança.</i>\n\n"
                f"1️⃣ <b>{top_2[0]['home']} x {top_2[0]['away']}</b> ({top_2[0]['horario']})\n"
                f"🎯 <b>Mercado:</b> {top_2[0]['mercado']} - {top_2[0]['selecao']}\n"
                f"📈 Odd: {top_2[0]['odd']:.2f}\n\n"
                f"2️⃣ <b>{top_2[1]['home']} x {top_2[1]['away']}</b> ({top_2[1]['horario']})\n"
                f"🎯 <b>Mercado:</b> {top_2[1]['mercado']} - {top_2[1]['selecao']}\n"
                f"📈 Odd: {top_2[1]['odd']:.2f}\n\n"
                f"🔥 <b>ODD TOTAL: {odd_total:.2f}</b>\n"
                f"💰 <b>Gestão recomendada:</b> 0.5% da Banca\n"
            )
            enviar_telegram(msg_multipla)
            jogos_enviados.add(id_multipla)

if __name__ == "__main__":
    inicializar_banco()
    print("🤖 Bot Institucional de Alta Performance Iniciado!")
    print("✅ Módulos Ativos: EV Restrito (Mínimo 2%) | Radar de 12 Horas | Qualidade Absoluta")
    while True:
        processar_jogos_e_enviar()
        verificar_resultados_automatico()
        time.sleep(600)