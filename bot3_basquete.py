import asyncio
import aiohttp
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ==========================================
# CONFIGURAÇÕES BOT 3 - BASQUETE
# ==========================================
API_KEYS_ODDS =[
    "6a1c0078b3ed09b42fbacee8f07e7cc3", "4949c49070dd3eff2113bd1a07293165",
    "0ecb237829d0f800181538e1a4fa2494", "4790419cc795932ffaeb0152fa5818c8",
    "5ee1c6a8c611b6c3d6aff8043764555f", "b668851102c3e0a56c33220161c029ec",
    "0d43575dd39e175ba670fb91b2230442", "d32378e66e89f159688cc2239f38a6a4",
    "713146de690026b224dd8bbf0abc0339"
]

TELEGRAM_TOKEN = "8413563055:AAGyovCDMJOxiAukTbXwaJPm3ZDckIf7qJU" # NOVO TOKEN BASQUETE
CHAT_ID = "-1003814625223"
DB_FILE = "probum.db"
SCAN_INTERVAL = 21600 # 6 Horas

SOFT_BOOKIES =["bet365","betano","1xbet","draftkings","williamhill","unibet","888sport","betfair_ex_eu"]
SHARP_BOOKIE = "pinnacle"
TODAS_CASAS = SOFT_BOOKIES +[SHARP_BOOKIE]

LEAGUE_TIERS = {"basketball_nba": 1.5, "basketball_euroleague": 1.2}
LIGAS = list(LEAGUE_TIERS.keys())

jogos_enviados = {}
historico_pinnacle = {} 
chave_odds_atual = 0 
api_lock = asyncio.Lock()
oportunidades_globais =[]

def carregar_memoria_banco():
    global jogos_enviados
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        cursor = conn.cursor()
        cursor.execute("SELECT id_aposta FROM operacoes_tipster WHERE status = 'PENDENTE'")
        for (id_aposta,) in cursor.fetchall():
            jogos_enviados[id_aposta.split("_")[0]] = datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(hours=24)
        conn.close()
    except: pass

def checar_limite_diario():
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        cursor = conn.cursor()
        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')
        cursor.execute("SELECT COUNT(*) FROM operacoes_tipster WHERE data_hora = ?", (hoje,))
        total_hoje = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM operacoes_tipster WHERE data_hora = ? AND esporte = 'basketball'", (hoje,))
        basket_hoje = cursor.fetchone()[0]
        conn.close()
        return total_hoje, basket_hoje
    except: return 0, 0

def salvar_aposta_banco(op, stake):
    try:
        conn = sqlite3.connect(DB_FILE, timeout=10)
        cursor = conn.cursor()
        id_aposta = f"{op['jogo_id']}_{op['mercado_nome'][:4]}_{op['selecao_nome'][:4]}".replace(" ", "")
        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')
        cursor.execute("""
            INSERT OR IGNORE INTO operacoes_tipster 
            (id_aposta, esporte, jogo, liga, mercado, selecao, odd, prob, ev, stake, status, lucro, data_hora, pinnacle_odd, ranking_score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDENTE', 0, ?, ?, ?)
        """, (id_aposta, op['esporte'], f"{op['home_team']} x {op['away_team']}", op['evento']['sport_title'], op['mercado_nome'], op['selecao_nome'], op['odd_bookie'], op['prob_justa'], op['ev_real'], stake, hoje, op.get('odd_pinnacle', 0), op.get('ranking_score', 0)))
        conn.commit()
        conn.close()
    except: pass

async def enviar_telegram_async(session, texto):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": texto, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: await session.post(url, json=payload, timeout=10)
    except: pass

async def fazer_requisicao_odds(session, url, parametros):
    global chave_odds_atual
    for _ in range(len(API_KEYS_ODDS)):
        async with api_lock: chave_teste = API_KEYS_ODDS[chave_odds_atual]
        parametros["apiKey"] = chave_teste
        try:
            async with session.get(url, params=parametros, timeout=15) as resposta:
                if resposta.status == 200: return await resposta.json()
                elif resposta.status in [401, 429]:
                    async with api_lock: chave_odds_atual = (chave_odds_atual + 1) % len(API_KEYS_ODDS)
                else: return await resposta.json()
        except: pass
    return None

def normalizar_nome(nome):
    if not isinstance(nome, str): return str(nome)
    return ''.join(c for c in unicodedata.normalize('NFD', nome) if unicodedata.category(c) != 'Mn').lower().strip()

def validar_basquete(odd, ev):
    if not (1.30 <= odd <= 15.00) or ev > 0.18: return False 
    return ev >= (0.015 if odd <= 2.10 else 0.025)

async def processar_liga_async(session, liga_key, agora_br):
    parametros = {"regions": "eu", "markets": "h2h,spreads,totals", "bookmakers": ",".join(TODAS_CASAS)}
    data = await fazer_requisicao_odds(session, f"https://api.the-odds-api.com/v4/sports/{liga_key}/odds/", parametros)
    if not isinstance(data, list): return

    for evento in data:
        jogo_id = str(evento['id'])
        if jogo_id in jogos_enviados: continue
        horario_br = datetime.fromisoformat(evento["commence_time"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Sao_Paulo"))
        minutos = (horario_br - agora_br).total_seconds() / 60
        if not (15 <= minutos <= 1440): continue 

        bookmakers = evento.get("bookmakers",[])
        pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)
        if not pinnacle: continue 

        dropping_alerts = {}
        for m in pinnacle.get("markets",[]):
            for out in m["outcomes"]:
                chave_hist = f"{jogo_id}_{m['key']}_{normalizar_nome(out['name'])}_{out.get('point','')}"
                preco_atual = out["price"]
                if chave_hist in historico_pinnacle and (historico_pinnacle[chave_hist]["price"] - preco_atual) / historico_pinnacle[chave_hist]["price"] >= 0.06:
                    dropping_alerts[chave_hist] = True
                historico_pinnacle[chave_hist] = {"price": preco_atual, "expires": agora_br + timedelta(hours=24)}

        oportunidades_jogo =[]
        for soft_b in bookmakers:
            if soft_b["key"] not in SOFT_BOOKIES: continue
            
            # Vencedor e Totais/Spreads (Basquete)
            for m_key in ["h2h", "spreads", "totals"]:
                pin_m = next((m for m in pinnacle.get("markets",[]) if m["key"] == m_key), None)
                soft_m = next((m for m in soft_b.get("markets",[]) if m["key"] == m_key), None)
                if pin_m and soft_m:
                    for s_out in soft_m["outcomes"]:
                        ponto = s_out.get("point")
                        n_out = normalizar_nome(s_out["name"])
                        
                        if m_key == "h2h":
                            margem = sum(1/i["price"] for i in pin_m["outcomes"] if i["price"]>0)
                            pin_match = next((p for p in pin_m["outcomes"] if normalizar_nome(p["name"]) == n_out), None)
                            if pin_match: prob_real = (1/pin_match["price"]) / margem
                            else: continue
                        else:
                            pin_match = next((p for p in pin_m["outcomes"] if normalizar_nome(p["name"]) == n_out and p.get("point") == ponto), None)
                            if not pin_match or not (1.50 <= pin_match["price"] <= 2.50): continue
                            par_pinnacle = [p for p in pin_m["outcomes"] if p.get("point") in (ponto, -ponto) or (m_key == "totals" and p.get("point") == ponto)]
                            prob_real = (1 / pin_match["price"]) / sum(1 / i["price"] for i in par_pinnacle if i["price"] > 0)
                            
                        odd_oferecida = s_out["price"]
                        ev_real = (prob_real * odd_oferecida) - 1
                        
                        if prob_real > 0 and validar_basquete(odd_oferecida, ev_real):
                            is_line_error = ev_real > 0.05 and m_key != "h2h" # Erro de linha gritante
                            is_dropping = dropping_alerts.get(f"{jogo_id}_{m_key}_{n_out}_{ponto if ponto else ''}", False)
                            
                            score = (ev_real * 100) * prob_real * LEAGUE_TIERS.get(liga_key, 1.0) * (1.3 if is_dropping else 1.0) * (1.5 if is_line_error else 1.0)
                            
                            nm = "Vencedor (1X2)" if m_key == "h2h" else ("Handicap (Spread)" if m_key == "spreads" else "Pontos Totais")
                            sn = s_out["name"] if m_key == "h2h" else f"{s_out['name']} {ponto}"
                            
                            oportunidades_jogo.append({
                                "jogo_id": jogo_id, "evento": evento, "home_team": evento["home_team"], "away_team": evento["away_team"],
                                "horario_br": horario_br, "minutos": minutos, "mercado_nome": nm, "selecao_nome": sn,
                                "odd_bookie": odd_oferecida, "odd_pinnacle": pin_match["price"], "prob_justa": prob_real, "ev_real": ev_real,
                                "nome_bookie": soft_b["title"], "is_dropping": is_dropping, "is_line_error": is_line_error,
                                "ranking_score": score, "esporte": "basketball"
                            })
        if oportunidades_jogo:
            oportunidades_globais.append(max(oportunidades_jogo, key=lambda x: x["ranking_score"]))

async def varrer_e_enviar():
    global jogos_enviados, historico_pinnacle
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    jogos_enviados = {k: v for k, v in jogos_enviados.items() if agora_br <= v}
    historico_pinnacle = {k: v for k, v in historico_pinnacle.items() if agora_br <= v["expires"]}
    oportunidades_globais.clear()
    
    async with aiohttp.ClientSession() as session:
        await asyncio.gather(*[processar_liga_async(session, l, agora_br) for l in LIGAS])

        if oportunidades_globais:
            # Multiplas Basquete
            cand_mult = [op for op in oportunidades_globais if op["odd_bookie"] <= 1.70 and op["prob_justa"] >= 0.60]
            jogos_mult_ids =[]
            if len(cand_mult) >= 2:
                cand_mult.sort(key=lambda x: x["ranking_score"], reverse=True)
                j_mult = cand_mult[:3]
                jogos_mult_ids = [op["jogo_id"] for op in j_mult]
                odd_t = 1.0
                txt_m = "🔥 <b>OPORTUNIDADE IMPERDÍVEL: MÚLTIPLA NBA/EURO</b> 🏀\n\n"
                for i, op in enumerate(j_mult, 1):
                    odd_t *= op["odd_bookie"]
                    txt_m += f"🏀 <b>Jogo {i}: {op['home_team']} x {op['away_team']}</b>\n👉 <b>Entrada:</b> {op['mercado_nome']} - {op['selecao_nome']} ({op['nome_bookie'].title()})\n📈 <b>Odd:</b> {op['odd_bookie']:.2f}\n\n"
                txt_m += f"💵 <b>ODD TOTAL:</b> {odd_t:.2f}\n💰 <b>Gestão Sugerida:</b> 0.5% da Banca\n"
                await enviar_telegram_async(session, txt_m)
                for op in j_mult:
                    jogos_enviados[op["jogo_id"]] = agora_br + timedelta(hours=24)
                    salvar_aposta_banco(op, 0.5)

            # Singles Basquete com Controle Diário de 10
            singles = [op for op in oportunidades_globais if op["jogo_id"] not in jogos_mult_ids]
            singles.sort(key=lambda x: x["ranking_score"], reverse=True)
            
            total_hoje, basq_hoje = checar_limite_diario()
            vagas_restantes_global = max(0, 10 - total_hoje)
            
            # Tenta mandar 5 de basquete. Mas se futebol mandou pouco, ele usa.
            vagas_permitidas = min(5, vagas_restantes_global)
            
            if vagas_restantes_global > 0:
                singles_finais =[]
                for op in singles:
                    if len(singles_finais) < vagas_permitidas:
                        singles_finais.append(op)
                    elif len(singles_finais) < vagas_restantes_global and op["ranking_score"] > 2.0: # Erros bizarros roubam vaga
                        singles_finais.append(op)
                        
                singles_finais.sort(key=lambda x: x["horario_br"])
                
                for op in singles_finais:
                    ev = op["ev_real"]
                    if op["is_dropping"] or op["is_line_error"]: cb, cf, st = "📉 <b>🏀 SMART MONEY (ERRO DE LINHA)</b>", "🔥 ELITE", 2.0
                    elif ev >= 0.04: cb, cf, st = "🎯 <b>🏀 NBA/EURO: SNIPER</b>", "🔥 ELITE", 2.0
                    else: cb, cf, st = "💎 <b>🏀 NBA/EURO: SÓLIDA</b>", "💪 FORTE", 1.5

                    txt = (f"{cb}\n\n🏆 <b>Liga:</b> {op['evento']['sport_title']}\n⏰ <b>Horário:</b> {op['horario_br'].strftime('%H:%M')}\n"
                           f"⚔️ <b>Jogo:</b> {op['home_team']} x {op['away_team']}\n\n🎯 <b>Mercado:</b> {op['mercado_nome']}\n"
                           f"👉 <b>Entrada:</b> {op['selecao_nome']}\n🏛️ <b>Casa:</b> {op['nome_bookie'].upper()}\n"
                           f"📈 <b>Odd Atual:</b> {op['odd_bookie']:.2f}\n\n💰 <b>Gestão/Stake:</b> {st:.1f}%\n"
                           f"🛡️ <b>Confiança:</b> {cf}\n📊 <b>Valor (+EV):</b> +{ev*100:.2f}%\n✅ <b>Probabilidade:</b> {op['prob_justa']*100:.1f}%\n")
                    await enviar_telegram_async(session, txt)
                    jogos_enviados[op["jogo_id"]] = agora_br + timedelta(hours=24)
                    salvar_aposta_banco(op, st)

async def loop_infinito():
    # Atraso de 2 minutos para não rodar Exatamente no mesmo segundo que o bot de Futebol (Protege sua API e Banco)
    await asyncio.sleep(120)
    while True:
        print("\n🏀 BOT BASQUETE: VARREDURA INICIADA")
        await varrer_e_enviar()
        print(f"🏀 BOT BASQUETE: Dormindo por {SCAN_INTERVAL//3600}h...")
        await asyncio.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    carregar_memoria_banco()
    print("🤖 BOT BASQUETE SINDICATO V12 INICIADO (Aguardando 2 min para sincronia...)")
    asyncio.run(loop_infinito())