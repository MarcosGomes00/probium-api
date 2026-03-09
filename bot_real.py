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
except:
    pass

# ==========================================
# CONFIGURAÇÕES REAIS E INTEGRAÇÃO DB
# ==========================================
API_KEY_ODDS = "6a1c0078b3ed09b42fbacee8f07e7cc3"
TELEGRAM_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"
HISTORY_FILE = "bets_history.json"
DB_FILE = "probum.db"

# 🏆 LIGAS MASSIVAMENTE EXPANDIDAS (+Volume de Apostas)
LIGAS =[
    # Futebol Elite
    "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",              
    "soccer_germany_bundesliga", "soccer_france_ligue_one", "soccer_portugal_primeira_liga",
    "soccer_netherlands_eredivisie", "soccer_uefa_champs_league", "soccer_uefa_europa_league",
    
    # Futebol Américas
    "soccer_brazil_campeonato", "soccer_brazil_copa_do_brasil", "soccer_brazil_serie_b",
    "soccer_conmebol_copa_libertadores", "soccer_conmebol_copa_sudamericana",
    "soccer_argentina_primera_division", "soccer_mexico_ligamx", "soccer_usa_mls",
    
    # Futebol Alternativo (Onde as casas mais erram)
    "soccer_turkey_super_league", "soccer_belgium_first_div", "soccer_england_championship",
    
    # Basquete
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
    except Exception as e:
        print(f"Erro ao salvar no DB: {e}")

    try:
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                bets = json.load(f)
        else:
            bets =[]
        bets.append(bet_data)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(bets, f, indent=2)
    except:
        pass

def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        pass

def buscar_valor_linhas_asiaticas(pinnacle, bet365, nome_mercado):
    oportunidades =[]
    pin_market = next((m for m in pinnacle.get("markets",[]) if m["key"] == nome_mercado), None)
    b365_market = next((m for m in bet365.get("markets", []) if m["key"] == nome_mercado), None)

    if pin_market and b365_market and len(pin_market["outcomes"]) == 2:
        p_out1 = pin_market["outcomes"][0]
        p_out2 = pin_market["outcomes"][1]
        
        if "point" not in p_out1: return oportunidades
        
        margin = (1/p_out1["price"]) + (1/p_out2["price"])
        
        for b_out in b365_market["outcomes"]:
            if b_out["name"] == p_out1["name"] and b_out.get("point") == p_out1.get("point"):
                prob = (1/p_out1["price"]) / margin
                ev = (prob * b_out["price"]) - 1
                if ev > 0.02: 
                    nome_exibicao = f"Asiático {b_out['name']} {b_out['point']}"
                    oportunidades.append((nome_exibicao, b_out['name'], b_out["price"], prob, ev))
            
            elif b_out["name"] == p_out2["name"] and b_out.get("point") == p_out2.get("point"):
                prob = (1/p_out2["price"]) / margin
                ev = (prob * b_out["price"]) - 1
                if ev > 0.02: 
                    nome_exibicao = f"Asiático {b_out['name']} {b_out['point']}"
                    oportunidades.append((nome_exibicao, b_out['name'], b_out["price"], prob, ev))
                    
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
            conn.close()
            return

        esportes_pendentes = set([p[1] for p in pendentes])
        
        for esporte in esportes_pendentes:
            url = f"https://api.the-odds-api.com/v4/sports/{esporte}/scores/"
            resp = requests.get(url, params={"apiKey": API_KEY_ODDS, "daysFrom": 1}, timeout=15)
            if resp.status_code != 200: continue
            scores_data = resp.json()

            for aposta in pendentes:
                id_ap, esp, jogo_nome, mercado, selecao, odd, stake = aposta
                if esp != esporte: continue
                
                times = jogo_nome.split(" x ")
                if len(times) != 2: continue
                home_t, away_t = times[0], times[1]

                game = next((g for g in scores_data if g["home_team"] == home_t and g["away_team"] == away_t), None)
                if not game or not game.get("completed") or not game.get("scores"): continue
                
                scores = game.get("scores")
                home_score = int(next((s["score"] for s in scores if s["name"] == home_t), 0))
                away_score = int(next((s["score"] for s in scores if s["name"] == away_t), 0))
                
                res_final = "RED"
                lucro = -stake
                
                if "Vitória Casa" in mercado and home_score > away_score: res_final = "GREEN"
                elif "Vitória Visitante" in mercado and away_score > home_score: res_final = "GREEN"
                elif "Asiático" in mercado:
                    soma = home_score + away_score
                    if "Over" in mercado:
                        linha = float(mercado.split()[-1])
                        if soma > linha: res_final = "GREEN"
                    elif "Under" in mercado:
                        linha = float(mercado.split()[-1])
                        if soma < linha: res_final = "GREEN"

                if res_final == "GREEN":
                    lucro = stake * (odd - 1)

                cursor.execute("UPDATE operacoes_tipster SET status = ?, lucro = ? WHERE id_aposta = ?", (res_final, lucro, id_ap))
                conn.commit()

                if res_final == "GREEN":
                    enviar_telegram(f"✅ <b>GREEN! LUCRO NO BOLSO!</b> 💰\n⚽ {jogo_nome} ({home_score}x{away_score})\n🎯 Bateu: {mercado}\n📈 +{lucro:.2f} Unidades.")
                else:
                    enviar_telegram(f"❌ <b>RED</b>\n⚽ {jogo_nome} ({home_score}x{away_score})\n🎯 Mercado: {mercado} não bateu.")
                    
        conn.close()
    except Exception as e:
        print(f"Erro checagem DB: {e}")

def processar_jogos_e_enviar():
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    print(f"\n🔄[ATUALIZAÇÃO - {agora_br.strftime('%H:%M:%S')}] Escaneando radar de 12 horas...")

    for liga in LIGAS:
        is_nba = "basketball" in liga
        mercados_alvo = "h2h,totals,spreads,player_points" if is_nba else "h2h,totals,spreads,btts"
        
        url = f"https://api.the-odds-api.com/v4/sports/{liga}/odds/"
        parametros = {"apiKey": API_KEY_ODDS, "regions": "eu,uk,us", "markets": mercados_alvo, "bookmakers": "bet365,pinnacle"}

        try:
            resposta = requests.get(url, params=parametros, timeout=15)
            if resposta.status_code != 200: continue
            dados = resposta.json()

            for evento in dados:
                horario_br = datetime.fromisoformat(evento["commence_time"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Sao_Paulo"))
                if horario_br < agora_br: continue

                bookmakers = evento.get("bookmakers",[])
                pinnacle = next((b for b in bookmakers if b["key"] == "pinnacle"), None)
                bet365 = next((b for b in bookmakers if b["key"] == "bet365"), next((b for b in bookmakers if b["key"] == "draftkings"), None))
                
                if not pinnacle or not bet365: continue

                home_team, away_team = evento["home_team"], evento["away_team"]
                oportunidades =[]

                oportunidades.extend(buscar_valor_linhas_asiaticas(pinnacle, bet365, "spreads"))
                oportunidades.extend(buscar_valor_linhas_asiaticas(pinnacle, bet365, "totals"))
                
                if is_nba:
                    oportunidades.extend(buscar_valor_linhas_asiaticas(pinnacle, bet365, "player_points"))

                pin_h2h = next((m for m in pinnacle.get("markets", []) if m["key"] == "h2h"), None)
                b365_h2h = next((m for m in bet365.get("markets",[]) if m["key"] == "h2h"), None)
                
                if pin_h2h and b365_h2h and len(pin_h2h["outcomes"]) >= 2:
                    p_odds, b_odds = pin_h2h["outcomes"], b365_h2h["outcomes"]
                    
                    pin_h = next((i["price"] for i in p_odds if i["name"] == home_team), 0)
                    pin_a = next((i["price"] for i in p_odds if i["name"] == away_team), 0)
                    pin_d = next((i["price"] for i in p_odds if i["name"] == "Draw"), 0)
                    
                    b365_h = next((i["price"] for i in b_odds if i["name"] == home_team), 0)
                    b365_a = next((i["price"] for i in b_odds if i["name"] == away_team), 0)

                    if pin_h > 0 and pin_a > 0:
                        margin = (1/pin_h) + (1/pin_a) + (1/pin_d if pin_d else 0)
                        prob_h, prob_a = (1/pin_h) / margin, (1/pin_a) / margin
                        
                        ev_h = (prob_h * b365_h) - 1 if b365_h else -1
                        ev_a = (prob_a * b365_a) - 1 if b365_a else -1

                        if ev_h > 0.02: oportunidades.append(("Vitória Casa", home_team, b365_h, prob_h, ev_h))
                        if ev_a > 0.02: oportunidades.append(("Vitória Visitante", away_team, b365_a, prob_a, ev_a))

                if not oportunidades: continue
                melhor_op = max(oportunidades, key=lambda x: x[4]) 
                mercado_nome, selecao_nome, odd_b365, prob_justa, ev_real = melhor_op

                b_kelly = odd_b365 - 1
                q_kelly = 1 - prob_justa
                kelly_pct = max(0.5, min(((prob_justa - (q_kelly / b_kelly)) * 0.25) * 100, 3.0))

                jogo_id = f"{evento['id']}_{mercado_nome}"
                minutos_faltando = (horario_br - agora_br).total_seconds() / 60

                # ⚠️ ATENÇÃO: AQUI ESTÁ A GRANDE MUDANÇA (Radar de 12 horas - 720 minutos)
                if 30 <= minutos_faltando <= 720:
                    if jogo_id not in jogos_enviados:
                        emoji = "🏀" if is_nba else "⚽"
                        
                        # Calcula as horas/minutos para formatar bonitinho no Telegram
                        horas_f = int(minutos_faltando // 60)
                        min_f = int(minutos_faltando % 60)
                        tempo_str = f"{horas_f}h {min_f}min" if horas_f > 0 else f"{min_f} min"

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
                        )
                        enviar_telegram(texto_msg)
                        jogos_enviados.add(jogo_id)

                        salvar_aposta_sistema({
                            "id": evento["id"],
                            "sport_key": liga,
                            "home": home_team,
                            "away": away_team,
                            "league": evento['sport_title'],
                            "market_chosen": mercado_nome,
                            "selecao": selecao_nome,
                            "odd": round(odd_b365, 2),
                            "prob": prob_justa, 
                            "ev": ev_real,           
                            "stake_perc": round(kelly_pct, 2),
                            "date": horario_br.strftime('%d/%m/%Y')
                        })
                        print(f"🚀 Tip enviada: {mercado_nome} | EV: +{ev_real*100:.2f}% | Faltam {tempo_str}")

        except Exception as e:
            pass

if __name__ == "__main__":
    inicializar_banco()
    print("🤖 Bot Institucional Iniciado com Sucesso!")
    print("✅ Radar Ampliado: 12 Horas | Ligas Extras Ativadas | Auto-Green")
    while True:
        processar_jogos_e_enviar()
        verificar_resultados_automatico()
        time.sleep(600)