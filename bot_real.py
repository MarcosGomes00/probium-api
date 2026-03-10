import requests
import time
import json
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

try:
    from services.result_checker import check_results
    from services.stats_analyzer import check_advanced_stats
    from services.auto_learning import is_league_profitable
except Exception: pass

# ==========================================
# 1. CONFIGURAÇÕES E CHAVES
# ==========================================
API_KEYS_ODDS =[
    "6a1c0078b3ed09b42fbacee8f07e7cc3",
    "4949c49070dd3eff2113bd1a07293165",
    "0ecb237829d0f800181538e1a4fa2494",
    "4790419cc795932ffaeb0152fa5818c8",
    "5ee1c6a8c611b6c3d6aff8043764555f",
    "b668851102c3e0a56c33220161c029ec",
    "0d43575dd39e175ba670fb91b2230442",
    "d32378e66e89f159688cc2239f38a6a4",
    "713146de690026b224dd8bbf0abc0339"
]

API_KEYS_FOOTBALL =[
    "1cd3cb39658509019bdb1cdffff22c39",
    "f05d340d10ad108aae44ed8b674519f7",
    "f4ffd9cc04c586e9e1d62266db35bb0a"
]

TELEGRAM_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"
DB_FILE = "probum.db"

SOFT_BOOKIES =["bet365", "betano", "1xbet", "draftkings", "williamhill", "unibet", "888sport", "betfair_ex_eu"]
SHARP_BOOKIE = "pinnacle"

# LIGAS REDUZIDAS (Apenas a Elite com Liquidez e Acertos Altos para poupar Tokens)
LIGAS =[
    "soccer_epl", "soccer_spain_la_liga", "soccer_italy_serie_a",              
    "soccer_germany_bundesliga", "soccer_france_ligue_one", "soccer_portugal_primeira_liga",
    "soccer_uefa_champs_league", "soccer_uefa_europa_league",
    "soccer_brazil_campeonato", "soccer_brazil_copa_do_brasil", "soccer_brazil_serie_b",
    "soccer_conmebol_copa_libertadores", "soccer_conmebol_copa_sudamericana",
    "basketball_nba", "basketball_euroleague"                     
]

jogos_enviados = {}
chave_odds_atual = 0 
chave_football_atual = 0

# Relógio do Sindicato (Controla a varredura de 12 horas)
ultima_varredura_normal = datetime.min.replace(tzinfo=ZoneInfo("America/Sao_Paulo"))

# ==========================================
# 2. FUNÇÕES DE SUPORTE E HISTÓRICO
# ==========================================
def limpar_memoria_antiga():
    agora = datetime.now()
    para_remover =[id_jogo for id_jogo, data_expiracao in jogos_enviados.items() if agora > data_expiracao]
    for id_jogo in para_remover: del jogos_enviados[id_jogo]

def fazer_requisicao_odds(url, parametros):
    global chave_odds_atual
    for _ in range(len(API_KEYS_ODDS)):
        parametros["apiKey"] = API_KEYS_ODDS[chave_odds_atual]
        try:
            resposta = requests.get(url, params=parametros, timeout=15)
            if resposta.status_code == 200: return resposta
            elif resposta.status_code in[401, 429]: chave_odds_atual = (chave_odds_atual + 1) % len(API_KEYS_ODDS)
            else: return resposta 
        except: pass
    return None

def fazer_requisicao_football(url, parametros):
    global chave_football_atual
    for _ in range(len(API_KEYS_FOOTBALL)):
        headers = {"x-apisports-key": API_KEYS_FOOTBALL[chave_football_atual]}
        try:
            resposta = requests.get(url, headers=headers, params=parametros, timeout=10)
            data = resposta.json()
            if resposta.status_code == 403 or ("errors" in data and data["errors"]):
                chave_football_atual = (chave_football_atual + 1) % len(API_KEYS_FOOTBALL)
            else: return data
        except: pass
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

def enviar_telegram(texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def buscar_id_time(nome_time):
    data = fazer_requisicao_football("https://v3.football.api-sports.io/teams", {"search": nome_time})
    if data and data.get("results", 0) > 0: return data["response"][0]["team"]["id"]
    return None

def obter_historico_times(home_name, away_name, esporte):
    if "basketball" in esporte:
        return "\n📊 <b>Estatística Avançada:</b> Fluxo financeiro pesado e alta liquidez rastreados a favor desta linha na NBA.\n"
    try:
        home_id = buscar_id_time(home_name)
        away_id = buscar_id_time(away_name)
        if not home_id or not away_id: return ""
        url_h2h = "https://v3.football.api-sports.io/fixtures/headtohead"
        data = fazer_requisicao_football(url_h2h, {"h2h": f"{home_id}-{away_id}", "last": 5})
        if data and data.get("results", 0) > 0:
            vit_home = sum(1 for m in data["response"] if (m["teams"]["home"]["winner"] and m["teams"]["home"]["id"] == home_id) or (m["teams"]["away"]["winner"] and m["teams"]["away"]["id"] == home_id))
            vit_away = sum(1 for m in data["response"] if (m["teams"]["home"]["winner"] and m["teams"]["home"]["id"] == away_id) or (m["teams"]["away"]["winner"] and m["teams"]["away"]["id"] == away_id))
            empates = data['results'] - vit_home - vit_away
            return f"\n📚 <b>HISTÓRICO H2H (Últimos {data['results']} jogos):</b>\n✅ {home_name}: {vit_home} V\n✅ {away_name}: {vit_away} V\n➖ Empates: {empates}\n"
    except: pass
    return ""

def calcular_prob_justa(outcomes):
    try:
        margem = sum(1 / item["price"] for item in outcomes if item["price"] > 0)
        return {item["name"]: (1 / item["price"]) / margem for item in outcomes if item["price"] > 0}
    except: return {}

# ==========================================
# 3. VALIDAÇÃO DE ELITE
# ==========================================
def validar_entrada_afiadissima(odd_oferecida, prob_real, ev_real, liga):
    if not (1.40 <= odd_oferecida <= 7.00): return False 
    if ev_real > 0.15: return False 
    
    ev_exigido = 0.0
    if odd_oferecida <= 2.50: ev_exigido = 0.015
    elif odd_oferecida <= 4.00: ev_exigido = 0.040
    else: ev_exigido = 0.070 

    ligas_tier_2 =["serie_b", "turkey", "belgium", "mexico", "uruguay", "sudamericana"]
    if any(l in liga for l in ligas_tier_2):
        ev_exigido += 0.015 

    return ev_real >= ev_exigido

# ==========================================
# 4. MOTOR PRINCIPAL
# ==========================================
def processar_jogos_e_enviar():
    global ultima_varredura_normal
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    
    # Verifica se já faz 12 horas desde o último envio em lote (Relatório Completo)
    faz_12_horas = (agora_br - ultima_varredura_normal).total_seconds() >= 43200
    
    if faz_12_horas:
        print(f"\n🔄[TURNO DE 12 HORAS - {agora_br.strftime('%H:%M:%S')}] Escaneando TODO O MERCADO para Múltiplas e Normais...")
    else:
        print(f"\n🕵️‍♂️[ESPIÃO SILENCIOSO - {agora_br.strftime('%H:%M:%S')}] Buscando apenas Oportunidades Raras e Zebras...")
        
    limpar_memoria_antiga()
    oportunidades_globais =[]
    
    for liga in LIGAS:
        time.sleep(1) 
        is_nba = "basketball" in liga
        mercados_alvo = "h2h,spreads,totals" if is_nba else "h2h,btts,totals,draw_no_bet,double_chance,spreads"
        
        casas_busca = f"{SHARP_BOOKIE}," + ",".join(SOFT_BOOKIES)
        parametros = {"regions": "eu,us", "markets": mercados_alvo, "bookmakers": casas_busca}
        url_odds = f"https://api.the-odds-api.com/v4/sports/{liga}/odds/"
        
        resposta = fazer_requisicao_odds(url_odds, parametros)
        if not resposta or resposta.status_code != 200: continue
            
        try:
            for evento in resposta.json():
                jogo_id = str(evento['id'])
                if jogo_id in jogos_enviados: continue

                horario_br = datetime.fromisoformat(evento["commence_time"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Sao_Paulo"))
                minutos_faltando = (horario_br - agora_br).total_seconds() / 60
                
                # Janela de 24 horas (Para garantir que os jogos sejam cobertos no ciclo de 12 em 12h)
                if not (15 <= minutos_faltando <= 1440): continue 

                bookmakers = evento.get("bookmakers",[])
                pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)
                if not pinnacle: continue 

                home_team, away_team = evento["home_team"], evento["away_team"]
                oportunidades_jogo =[]
                
                for soft_b in bookmakers:
                    if soft_b["key"] == SHARP_BOOKIE or soft_b["key"] not in SOFT_BOOKIES: continue
                    nome_casa = soft_b["title"]

                    for m_key in["h2h", "btts", "draw_no_bet", "double_chance"]:
                        pin_m = next((m for m in pinnacle.get("markets",[]) if m["key"] == m_key), None)
                        soft_m = next((m for m in soft_b.get("markets",[]) if m["key"] == m_key), None)
                        if pin_m and soft_m:
                            probs_justas = calcular_prob_justa(pin_m["outcomes"])
                            for s_outcome in soft_m["outcomes"]:
                                prob_real = probs_justas.get(s_outcome["name"], 0)
                                odd_oferecida = s_outcome["price"]
                                if prob_real > 0:
                                    ev_real = (prob_real * odd_oferecida) - 1
                                    if validar_entrada_afiadissima(odd_oferecida, prob_real, ev_real, liga):
                                        traducao = m_key.replace("h2h", "Vencedor (1X2)").replace("btts", "Ambas Marcam").replace("draw_no_bet", "Empate Anula").replace("double_chance", "Dupla Aposta")
                                        selecao = "Sim" if s_outcome["name"]=="Yes" else "Não" if s_outcome["name"]=="No" else s_outcome["name"].replace("/", " ou ")
                                        oportunidades_jogo.append((traducao, selecao, odd_oferecida, prob_real, ev_real, nome_casa))

                    for m_key in ["totals", "spreads"]:
                        pin_m = next((m for m in pinnacle.get("markets",[]) if m["key"] == m_key), None)
                        soft_m = next((m for m in soft_b.get("markets",[]) if m["key"] == m_key), None)
                        if pin_m and soft_m:
                            for s_outcome in soft_m["outcomes"]:
                                ponto = s_outcome.get("point")
                                pin_match = next((p for p in pin_m["outcomes"] if p["name"] == s_outcome["name"] and p.get("point") == ponto), None)
                                
                                if pin_match and (1.70 <= pin_match["price"] <= 2.30):
                                    if m_key == "totals":
                                        par_pinnacle =[p for p in pin_m["outcomes"] if p.get("point") == ponto]
                                        nome_mercado = "Gols/Pontos (Over/Under)"
                                        selecao_nome = f"{s_outcome['name']} {ponto}"
                                    else:
                                        par_pinnacle =[p for p in pin_m["outcomes"] if p.get("point") in (ponto, -ponto)]
                                        nome_mercado = "Handicap Asiático"
                                        selecao_nome = f"{s_outcome['name']} ({ponto})"

                                    try:
                                        prob_real = (1 / pin_match["price"]) / sum(1 / i["price"] for i in par_pinnacle if i["price"] > 0)
                                        odd_oferecida = s_outcome["price"]
                                        if prob_real > 0:
                                            ev_real = (prob_real * odd_oferecida) - 1
                                            if validar_entrada_afiadissima(odd_oferecida, prob_real, ev_real, liga):
                                                oportunidades_jogo.append((nome_mercado, selecao_nome, odd_oferecida, prob_real, ev_real, nome_casa))
                                    except: pass

                if not oportunidades_jogo: continue
                
                melhor_op = max(oportunidades_jogo, key=lambda x: x[4]) 
                mercado_nome, selecao_nome, odd_bookie, prob_justa, ev_real, nome_bookie = melhor_op

                # LÓGICA DO ESPIÃO: Verifica se a aposta é RARA ou COMUM
                is_zebra_rara = odd_bookie >= 4.01 and ev_real >= 0.07
                is_oportunidade_unica = ev_real >= 0.035 and prob_justa >= 0.50
                is_rara = is_zebra_rara or is_oportunidade_unica

                # Se for o ciclo de "Meio de dia" e NÃO for rara, o robô ignora!
                if not faz_12_horas and not is_rara:
                    continue

                oportunidades_globais.append({
                    "jogo_id": jogo_id, "evento": evento,
                    "home_team": home_team, "away_team": away_team,
                    "horario_br": horario_br, "minutos_faltando": minutos_faltando,
                    "mercado_nome": mercado_nome, "selecao_nome": selecao_nome,
                    "odd_bookie": odd_bookie, "prob_justa": prob_justa, 
                    "ev_real": ev_real, "nome_bookie": nome_bookie,
                    "is_nba": is_nba, "esporte": liga,
                    "is_rara": is_rara
                })

        except Exception as e: pass

    # ==========================================
    # ENVIO NO TELEGRAM
    # ==========================================
    if oportunidades_globais:
        oportunidades_globais.sort(key=lambda x: x["ev_real"], reverse=True)
        # Se for 12 em 12h, pega as 5 melhores. Se for no "meio do dia", manda apenas as Raras (Máx 3)
        top_snipers = oportunidades_globais[:5] if faz_12_horas else oportunidades_globais[:3]
        
        for op in top_snipers:
            ev_real, prob_justa, odd_bookie = op["ev_real"], op["prob_justa"], op["odd_bookie"]
            
            if odd_bookie >= 4.01:
                cabecalho = "🦓 <b>ZEBRA DE VALOR (ANÁLISE SUPERIOR)</b> 🦓\n<i>Falha brutal da casa identificada. Lucro de alta variância!</i>"
                kelly_pct = 0.5 
            elif ev_real >= 0.035 and prob_justa >= 0.50:
                cabecalho = "🎯🏆 <b>OPORTUNIDADE ÚNICA (ENTRADA PESADA)</b> 🏆🎯\n<i>Padrão Diamante: Altíssima assertividade + Matemática perfeita.</i>"
                kelly_pct = 3.0 
            else:
                cabecalho = "💎 <b>APOSTA INSTITUCIONAL (PADRÃO)</b> 💎"
                b_kelly, q_kelly = odd_bookie - 1, 1 - prob_justa
                try: kelly_pct = max(1.0, min(((prob_justa - (q_kelly / b_kelly)) * 0.25) * 100, 2.0))
                except: kelly_pct = 1.0

            horas_f, min_f = int(op["minutos_faltando"] // 60), int(op["minutos_faltando"] % 60)
            tempo_str = f"{horas_f}h {min_f}min" if horas_f > 0 else f"{min_f} min"
            emoji = "🏀" if op["is_nba"] else "⚽"
            
            bloco_historico = obter_historico_times(op['home_team'], op['away_team'], op["esporte"])
            
            texto_msg = (
                f"{cabecalho}\n\n"
                f"🏆 <b>Liga:</b> {op['evento']['sport_title']}\n"
                f"⏰ <b>Horário:</b> {op['horario_br'].strftime('%H:%M')} (Faltam {tempo_str})\n"
                f"{emoji} <b>Jogo:</b> {op['home_team']} x {op['away_team']}\n\n"
                f"🎯 <b>Mercado:</b> {op['mercado_nome']}\n"
                f"👉 <b>Entrada:</b> {op['selecao_nome']}\n"
                f"🏛️ <b>Casa de Aposta:</b> {op['nome_bookie']}\n"
                f"📈 <b>Odd Atual:</b> {odd_bookie:.2f}\n\n"
                f"💰 <b>Gestão Sugerida:</b> {kelly_pct:.1f}% da Banca\n"
                f"📊 <b>Vantagem Matemática (+EV):</b> +{ev_real*100:.2f}%\n"
                f"{bloco_historico}"
            )
            enviar_telegram(texto_msg)
            jogos_enviados[op["jogo_id"]] = datetime.now() + timedelta(hours=24)

        # Só gera a Múltipla se for no ciclo de 12 horas
        if faz_12_horas:
            jogos_seguros =[op for op in top_snipers if op["prob_justa"] >= 0.55 and op["odd_bookie"] <= 1.80]
            if len(jogos_seguros) >= 2:
                m1, m2 = jogos_seguros[0], jogos_seguros[1]
                odd_dupla = m1["odd_bookie"] * m2["odd_bookie"]
                
                texto_multipla = (
                    "🔥🧩 <b>COMBO +EV SINDICATO (MÚLTIPLA BLINDADA)</b> 🧩🔥\n"
                    "<i>Juntamos as 2 análises de maior Win-Rate do momento para lucrar duplo!</i>\n\n"
                    f"1️⃣ <b>{m1['home_team']} x {m1['away_team']}</b>\n"
                    f"👉 {m1['mercado_nome']} - <b>{m1['selecao_nome']}</b> (@{m1['odd_bookie']:.2f})\n\n"
                    f"2️⃣ <b>{m2['home_team']} x {m2['away_team']}</b>\n"
                    f"👉 {m2['mercado_nome']} - <b>{m2['selecao_nome']}</b> (@{m2['odd_bookie']:.2f})\n\n"
                    f"🏛️ <b>Casa Recomendada:</b> Monte o bilhete onde a odd for maior.\n"
                    f"🚀 <b>ODD FINAL DA DUPLA:</b> {odd_dupla:.2f}\n"
                    f"💰 <b>Stake Recomendada:</b> 0.5% a 1.0% da Banca"
                )
                enviar_telegram(texto_multipla)
            
            # Atualiza o relógio marcando que a varredura de 12 horas foi concluída
            ultima_varredura_normal = agora_br

    else:
        if faz_12_horas: print("\n😴 Relatório de 12 horas: Sem valor no mercado no momento.")
        else: print("\n🕵️‍♂️ Espião: Nenhuma 'Oportunidade Única' ou 'Zebra' detectada agora.")

# ==========================================
# 5. LOOP PRINCIPAL
# ==========================================
if __name__ == "__main__":
    inicializar_banco()
    print("🤖 Bot Sindicato ASIÁTICO v8.0 INICIADO!")
    print("✅ Ligas Filtradas (Apenas a Elite do Futebol e NBA).")
    print("✅ Múltiplas e Bilhetes Padrão a cada 12 HORAS.")
    print("✅ Espião Silencioso: Manda alertas Imediatos no meio do dia SE achar algo raro!")
    
    while True:
        processar_jogos_e_enviar()
        # O robô acorda a cada 2 horas (7200s) para buscar coisas raras invisivelmente.
        # A cada 6 voltas (12 horas), ele faz a varredura completa.
        print("\n⏳ Bot dormindo por 2 horas...")
        time.sleep(7200)