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

# Memória inteligente (Evita Spam)
jogos_enviados = {}
chave_odds_atual = 0 
chave_football_atual = 0

# ==========================================
# 2. GERENCIADORES E BANCO DE DADOS
# ==========================================
def limpar_memoria_antiga():
    """Remove jogos antigos da memória para não vazar RAM no servidor"""
    agora = datetime.now()
    para_remover =[id_jogo for id_jogo, data_expiracao in jogos_enviados.items() if agora > data_expiracao]
    for id_jogo in para_remover:
        del jogos_enviados[id_jogo]

def fazer_requisicao_odds(url, parametros):
    global chave_odds_atual
    for _ in range(len(API_KEYS_ODDS)):
        parametros["apiKey"] = API_KEYS_ODDS[chave_odds_atual]
        try:
            resposta = requests.get(url, params=parametros, timeout=15)
            if resposta.status_code == 200:
                restantes = resposta.headers.get('x-requests-remaining', '?')
                print(f"📡 [Odds API] OK! (Restam {restantes} reqs)")
                return resposta
            elif resposta.status_code in [401, 429]:
                chave_odds_atual = (chave_odds_atual + 1) % len(API_KEYS_ODDS)
            else:
                return resposta 
        except Exception: pass
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
            else:
                return data
        except Exception: pass
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

def obter_historico_times(home_name, away_name):
    # Busca simplificada usando string exata (se a API Football aceitar)
    # Recomendado manter vazio se gerar muito custo de requisição, deixei ativado com tratamento de erro.
    try:
        return "" # Mantido em branco para poupar requests extras. Ative se precisar do H2H de volta.
    except: return ""

def calcular_prob_justa(outcomes):
    try:
        margem = sum(1 / item["price"] for item in outcomes if item["price"] > 0)
        return {item["name"]: (1 / item["price"]) / margem for item in outcomes if item["price"] > 0}
    except: return {}

# ==========================================
# 3. MOTOR DE ANÁLISE +EV E BUSCA MULTI-BOOKIES
# ==========================================
def validar_entrada_afiadissima(odd_oferecida, ev_real):
    """ Regra de Ouro do Sniper: Escalonamento de Risco x Valor """
    if not (1.50 <= odd_oferecida <= 5.00): 
        return False
    if ev_real > 0.12: 
        return False # Suspeita de lesão ou odd desatualizada
        
    if odd_oferecida <= 2.20:
        return ev_real >= 0.015 # Favoritos: Pede 1.5% de EV
    elif odd_oferecida <= 3.50:
        return ev_real >= 0.035 # Intermediárias: Pede 3.5% de EV
    elif odd_oferecida <= 5.00:
        return ev_real >= 0.050 # ZEBRAS: Exige 5.0% de EV no mínimo!
    return False

def processar_jogos_e_enviar():
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    print(f"\n🔄[ATUALIZAÇÃO - {agora_br.strftime('%H:%M:%S')}] Escaneando Valor Global (Filtro Sniper Ativado)...")
    limpar_memoria_antiga()
    
    LIMITE_POR_VARREDURA = 3  
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
                if jogo_id in jogos_enviados: continue # Anti-Spam: Pula se já enviou no dia

                horario_br = datetime.fromisoformat(evento["commence_time"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Sao_Paulo"))
                minutos_faltando = (horario_br - agora_br).total_seconds() / 60
                
                # Janela de Oportunidade: De 15 min até 24 horas antes do jogo
                if not (15 <= minutos_faltando <= 1440): continue 

                bookmakers = evento.get("bookmakers",[])
                pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)
                if not pinnacle: continue 

                home_team, away_team = evento["home_team"], evento["away_team"]
                oportunidades_jogo =[]
                
                for soft_b in bookmakers:
                    if soft_b["key"] == SHARP_BOOKIE or soft_b["key"] not in SOFT_BOOKIES: continue
                    nome_casa = soft_b["title"]

                    # --- 1. MATCH ODDS (H2H), BTTS, DNB e DC (Lógica Simples) ---
                    mercados_simples = ["h2h", "btts", "draw_no_bet", "double_chance"]
                    for m_key in mercados_simples:
                        pin_m = next((m for m in pinnacle.get("markets",[]) if m["key"] == m_key), None)
                        soft_m = next((m for m in soft_b.get("markets",[]) if m["key"] == m_key), None)
                        if pin_m and soft_m:
                            probs_justas = calcular_prob_justa(pin_m["outcomes"])
                            for s_outcome in soft_m["outcomes"]:
                                prob_real = probs_justas.get(s_outcome["name"], 0)
                                odd_oferecida = s_outcome["price"]
                                if prob_real > 0:
                                    ev_real = (prob_real * odd_oferecida) - 1
                                    if validar_entrada_afiadissima(odd_oferecida, ev_real):
                                        # Traduz os mercados
                                        traducao = m_key.replace("h2h", "Vencedor (1X2)").replace("btts", "Ambas Marcam").replace("draw_no_bet", "Empate Anula").replace("double_chance", "Dupla Aposta")
                                        selecao = "Sim" if s_outcome["name"]=="Yes" else "Não" if s_outcome["name"]=="No" else s_outcome["name"].replace("/", " ou ")
                                        oportunidades_jogo.append((traducao, selecao, odd_oferecida, prob_real, ev_real, nome_casa))

                    # --- 2. TOTALS (OVER/UNDER) ---
                    pin_tot = next((m for m in pinnacle.get("markets",[]) if m["key"] == "totals"), None)
                    soft_tot = next((m for m in soft_b.get("markets",[]) if m["key"] == "totals"), None)
                    if pin_tot and soft_tot:
                        for s_outcome in soft_tot["outcomes"]:
                            ponto = s_outcome.get("point")
                            pin_match = next((p for p in pin_tot["outcomes"] if p["name"] == s_outcome["name"] and p.get("point") == ponto), None)
                            if pin_match:
                                par_pinnacle = [p for p in pin_tot["outcomes"] if p.get("point") == ponto]
                                try:
                                    prob_real = (1 / pin_match["price"]) / sum(1 / i["price"] for i in par_pinnacle if i["price"] > 0)
                                    odd_oferecida = s_outcome["price"]
                                    if prob_real > 0:
                                        ev_real = (prob_real * odd_oferecida) - 1
                                        if validar_entrada_afiadissima(odd_oferecida, ev_real):
                                            oportunidades_jogo.append(("Gols/Pontos", f"{s_outcome['name']} {ponto}", odd_oferecida, prob_real, ev_real, nome_casa))
                                except: pass

                    # --- 3. HANDICAP ASIÁTICO (SPREADS) ---
                    pin_spread = next((m for m in pinnacle.get("markets", []) if m["key"] == "spreads"), None)
                    soft_spread = next((m for m in soft_b.get("markets",[]) if m["key"] == "spreads"), None)
                    if pin_spread and soft_spread:
                        for s_outcome in soft_spread["outcomes"]:
                            ponto = s_outcome.get("point")
                            selecao_nome = f"{s_outcome['name']} ({ponto})"
                            pin_match = next((p for p in pin_spread["outcomes"] if p["name"] == s_outcome["name"] and p.get("point") == ponto), None)
                            if pin_match:
                                # Handicap precisa do ponto exato oposto (ex: -1.5 e +1.5) para remover o Juice
                                par_pinnacle = [p for p in pin_spread["outcomes"] if p.get("point") in (ponto, -ponto)]
                                try:
                                    prob_real = (1 / pin_match["price"]) / sum(1 / i["price"] for i in par_pinnacle if i["price"] > 0)
                                    odd_oferecida = s_outcome["price"]
                                    if prob_real > 0:
                                        ev_real = (prob_real * odd_oferecida) - 1
                                        if validar_entrada_afiadissima(odd_oferecida, ev_real):
                                            oportunidades_jogo.append(("Handicap Asiático", selecao_nome, odd_oferecida, prob_real, ev_real, nome_casa))
                                except: pass

                if not oportunidades_jogo: continue
                
                # Para evitar spam, pega apenas a melhor aposta disparada DESTE JOGO em específico
                melhor_op = max(oportunidades_jogo, key=lambda x: x[4]) 
                mercado_nome, selecao_nome, odd_bookie, prob_justa, ev_real, nome_bookie = melhor_op

                oportunidades_globais.append({
                    "jogo_id": jogo_id, "evento": evento,
                    "home_team": home_team, "away_team": away_team,
                    "horario_br": horario_br, "minutos_faltando": minutos_faltando,
                    "mercado_nome": mercado_nome, "selecao_nome": selecao_nome,
                    "odd_bookie": odd_bookie, "prob_justa": prob_justa, 
                    "ev_real": ev_real, "nome_bookie": nome_bookie,
                    "is_nba": is_nba, "liga": liga
                })

        except Exception as e: 
            print(f"⚠️ Erro no processamento: {e}")

    # ==========================================
    # RANQUEAMENTO E ENVIO NO TELEGRAM
    # ==========================================
    if oportunidades_globais:
        # Ordena pegando os maiores EVs Globalmente
        oportunidades_globais.sort(key=lambda x: x["ev_real"], reverse=True)
        top_snipers = oportunidades_globais[:LIMITE_POR_VARREDURA]
        
        print(f"\n🎯 Achamos {len(oportunidades_globais)} oportunidades +EV. Disparando as {len(top_snipers)} melhores!")

        for op in top_snipers:
            ev_real = op["ev_real"]
            prob_justa = op["prob_justa"]
            odd_bookie = op["odd_bookie"]
            
            if odd_bookie > 3.50:
                cabecalho = "🦓 <b>ZEBRA DE VALOR (ALTA VARIÂNCIA)</b> 🦓"
            elif ev_real >= 0.05:
                cabecalho = "🚨🚨 <b>OPORTUNIDADE IMPERDÍVEL (MAX STAKE)</b> 🚨🚨"
            elif ev_real >= 0.025:
                cabecalho = "💎 <b>APOSTA INSTITUCIONAL (SNIPER)</b> 💎"
            else:
                cabecalho = "🔥 <b>OPORTUNIDADE DE VALOR (MODERADA)</b> 🔥"
            
            # Gestão de Banca: Protege em Odds altas, arrisca um pouco mais em favoritas (+EV)
            b_kelly = odd_bookie - 1
            q_kelly = 1 - prob_justa
            try: kelly_pct = max(0.2, min(((prob_justa - (q_kelly / b_kelly)) * 0.25) * 100, 3.0))
            except: kelly_pct = 0.5

            horas_f, min_f = int(op["minutos_faltando"] // 60), int(op["minutos_faltando"] % 60)
            tempo_str = f"{horas_f}h {min_f}min" if horas_f > 0 else f"{min_f} min"
            emoji = "🏀" if op["is_nba"] else "⚽"
            
            texto_msg = (
                f"{cabecalho}\n\n"
                f"🏆 <b>Liga:</b> {op['evento']['sport_title']}\n"
                f"⏰ <b>Horário:</b> {op['horario_br'].strftime('%H:%M')} (Faltam {tempo_str})\n"
                f"{emoji} <b>Jogo:</b> {op['home_team']} x {op['away_team']}\n\n"
                f"🎯 <b>Mercado:</b> {op['mercado_nome']}\n"
                f"👉 <b>Entrada:</b> {op['selecao_nome']}\n"
                f"🏛️ <b>Casa de Aposta:</b> {op['nome_bookie']}\n"
                f"📈 <b>Odd Atual:</b> {odd_bookie:.2f}\n\n"
                f"💰 <b>Gestão Recomendada:</b> {kelly_pct:.1f}% da Banca\n"
                f"📊 <b>Vantagem (+EV):</b> +{ev_real*100:.2f}%"
            )
            enviar_telegram(texto_msg)
            
            # Adiciona o ID na memória bloqueando repetições pelas próximas 24 horas
            jogos_enviados[op["jogo_id"]] = datetime.now() + timedelta(hours=24)

            salvar_aposta_sistema({
                "id": op["evento"]["id"], "sport_key": op["liga"], "home": op["home_team"], "away": op["away_team"],
                "league": op["evento"]['sport_title'], "market_chosen": op["mercado_nome"], "selecao": op["selecao_nome"],
                "odd": round(odd_bookie, 2), "prob": prob_justa, "ev": ev_real, "stake_perc": round(kelly_pct, 2),
                "date": op["horario_br"].strftime('%d/%m/%Y')
            })
            print(f"🚀 ✅ TIP ENVIADA: {op['home_team']} x {op['away_team']} | Odd: {odd_bookie:.2f} | EV: +{ev_real*100:.2f}%")
    else:
        print("\n😴 Nenhuma oportunidade com Análise Afiada encontrada nesta rodada.")

# ==========================================
# 4. LOOP PRINCIPAL
# ==========================================
if __name__ == "__main__":
    inicializar_banco()
    print("🤖 Bot Sniper Definitivo Iniciado com Sucesso!")
    print("✅ Filtro Anti-Spam Definitivo (1 ID = 1 Entrada) Ativado!")
    print("✅ Handicap Asiático Corrigido, Anti-Zebra Afiado e Max Stake Ativado!")
    
    while True:
        processar_jogos_e_enviar()
        print("\n⏳ Aguardando 6 horas para a próxima varredura global...")
        # 21600 segundos = 6 horas
        time.sleep(21600)