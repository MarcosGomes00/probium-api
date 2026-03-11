import asyncio
import aiohttp
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import Optional, List, Dict
import json

# ==========================================
# CONFIGURAÇÕES BOT 1 - FUTEBOL PRO
# ==========================================

# APIs THE-ODDS-API (9 chaves - rotação automática)
API_KEYS_ODDS = [
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

TELEGRAM_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"
DB_FILE = "probum.db"

SCAN_INTERVAL = 21600  # 6 horas
REQUEST_DELAY = 1.5  # Segundos entre requisições
MAX_REQ_POR_CHAVE_DIA = 80

SOFT_BOOKIES = [
    "bet365", "betano", "1xbet", "draftkings", 
    "williamhill", "unibet", "888sport", "betfair_ex_eu"
]

SHARP_BOOKIE = "pinnacle"
TODAS_CASAS = SOFT_BOOKIES + [SHARP_BOOKIE]

LEAGUE_TIERS = {
    "soccer_uefa_champs_league": 1.5,
    "soccer_epl": 1.5,
    "soccer_spain_la_liga": 1.2,
    "soccer_germany_bundesliga": 1.2,
    "soccer_italy_serie_a": 1.2,
    "soccer_brazil_campeonato": 1.0,
    "soccer_conmebol_copa_libertadores": 1.0,
    "soccer_france_ligue_one": 1.0,
    "soccer_portugal_primeira_liga": 1.0,
    "soccer_brazil_copa_do_brasil": 1.0,
    "soccer_netherlands_eredivisie": 1.1,
    "soccer_england_efl_championship": 1.1,
    "soccer_mexico_ligamx": 0.9,
    "soccer_argentina_primeradivision": 0.9,
    "soccer_belgium_first_division": 1.0,
    "soccer_turkey_super_lig": 1.0,
    "soccer_denmark_superliga": 0.9,
    "soccer_austria_bundesliga": 0.9
}

LIGAS = list(LEAGUE_TIERS.keys())

# ==========================================
# ESTRUTURAS E CONTROLE
# ==========================================

@dataclass
class EstatisticasTime:
    nome: str
    ultimos_jogos: List[Dict]
    media_gols_marcados: float
    media_gols_sofridos: float
    jogos_sem_sofrer_gol: int
    jogos_marcou_gol: int
    over_15: float
    over_25: float
    btts_sim: float
    forma: str
    xg_medio: Optional[float] = None
    posicao_tabela: Optional[int] = None

@dataclass
class AnaliseJogo:
    jogo_id: str
    home_team: str
    away_team: str
    liga: str
    horario_br: datetime
    stats_home: Optional[EstatisticasTime]
    stats_away: Optional[EstatisticasTime]
    h2h: List[Dict]
    mercado_nome: str
    selecao_nome: str
    odd_bookie: float
    odd_pinnacle: float
    nome_bookie: str
    prob_justa: float
    ev_real: float
    ranking_score: float
    nivel_confianca: str
    melhor_entrada: str
    mercados_interessantes: List[str]

jogos_enviados = {}
chave_odds_atual = 0
api_lock = asyncio.Lock()
request_count = {}
last_request_time = 0
chaves_falhas = set()  # Track de chaves que falharam (401/429)

# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================

def normalizar_nome(nome):
    if not isinstance(nome, str):
        return str(nome)
    return ''.join(
        c for c in unicodedata.normalize('NFD', nome)
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()

async def rate_limit():
    global last_request_time
    agora = datetime.now().timestamp()
    tempo_passado = agora - last_request_time
    if tempo_passado < REQUEST_DELAY:
        await asyncio.sleep(REQUEST_DELAY - tempo_passado)
    last_request_time = datetime.now().timestamp()

def calcular_nivel_confianca(ev: float, tier_liga: float, 
                             stats_home: Optional[EstatisticasTime],
                             stats_away: Optional[EstatisticasTime]) -> str:
    score = ev * 100
    if tier_liga >= 1.5:
        score += 5
    if stats_home and stats_away:
        consistencia = abs(stats_home.over_25 - stats_away.over_25)
        if consistencia < 15:
            score += 3
    if score >= 8:
        return "🔥 Alto"
    elif score >= 5:
        return "⚡ Médio"
    return "⚠️ Baixo"

def obter_mercados_interessantes(stats_home: EstatisticasTime, 
                                  stats_away: EstatisticasTime,
                                  h2h: List[Dict]) -> List[str]:
    mercados = []
    media_total_gols = (stats_home.media_gols_marcados + stats_home.media_gols_sofridos +
                       stats_away.media_gols_marcados + stats_away.media_gols_sofridos) / 2
    
    if media_total_gols > 2.8:
        mercados.append("Over 2.5 Gols")
    elif media_total_gols > 2.2:
        mercados.append("Over 1.5 Gols")
    elif media_total_gols < 2.0:
        mercados.append("Under 2.5 Gols")
    
    btts_media = (stats_home.btts_sim + stats_away.btts_sim) / 2
    if btts_media > 55:
        mercados.append("BTTS Sim")
    elif btts_media < 40:
        mercados.append("BTTS Não")
    
    if stats_home.forma.count('W') >= 3 and stats_away.forma.count('L') >= 3:
        mercados.append(f"Vitória {stats_home.nome}")
    elif stats_away.forma.count('W') >= 3 and stats_home.forma.count('L') >= 3:
        mercados.append(f"Vitória {stats_away.nome}")
    
    if stats_home.jogos_sem_sofrer_gol >= 3:
        mercados.append(f"Dupla Chance 1X")
    elif stats_away.jogos_sem_sofrer_gol >= 3:
        mercados.append(f"Dupla Chance X2")
    
    return mercados

# ==========================================
# BANCO DE DADOS
# ==========================================

def carregar_memoria_banco():
    global jogos_enviados
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id_aposta FROM operacoes_tipster WHERE status='PENDENTE'"
        )
        for (id_aposta,) in cursor.fetchall():
            jogos_enviados[id_aposta.split("_")[0]] = datetime.now(
                ZoneInfo("America/Sao_Paulo")
            ) + timedelta(hours=24)
        conn.close()
    except:
        pass

def salvar_aposta_banco(op, stake, analise):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        id_aposta = f"{op['jogo_id']}_{op['mercado_nome'][:4]}_{op['selecao_nome'][:4]}".replace(" ", "")
        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')
        
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
                status TEXT,
                lucro REAL,
                data_hora TEXT,
                pinnacle_odd REAL,
                ranking_score REAL,
                nivel_confianca TEXT,
                stats_home TEXT,
                stats_away TEXT,
                mercados_sugeridos TEXT
            )
        """)
        
        cursor.execute(
            """
            INSERT OR IGNORE INTO operacoes_tipster
            (id_aposta,esporte,jogo,liga,mercado,selecao,odd,prob,ev,stake,status,lucro,data_hora,pinnacle_odd,ranking_score,nivel_confianca,stats_home,stats_away,mercados_sugeridos)
            VALUES (?,?,?,?,?,?,?,?,?,?, 'PENDENTE',0,?,?,?,?,?,?,?)
            """,
            (
                id_aposta, "soccer", f"{op['home_team']} x {op['away_team']}",
                op["evento"]["sport_title"], op["mercado_nome"], op["selecao_nome"],
                op["odd_bookie"], op["prob_justa"], op["ev_real"], stake, hoje,
                op["odd_pinnacle"], op["ranking_score"], analise.nivel_confianca,
                json.dumps(analise.stats_home.__dict__ if analise.stats_home else {}),
                json.dumps(analise.stats_away.__dict__ if analise.stats_away else {}),
                json.dumps(analise.mercados_interessantes)
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar: {e}")

# ==========================================
# TELEGRAM
# ==========================================

async def enviar_telegram_async(session, analise: AnaliseJogo):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    stats_txt = ""
    if analise.stats_home and analise.stats_away:
        stats_txt = (
            f"\n📊 <b>Estatísticas:</b>\n"
            f"  {analise.home_team}: {analise.stats_home.media_gols_marcados:.1f} gols/jogo | Forma: {analise.stats_home.forma}\n"
            f"  {analise.away_team}: {analise.stats_away.media_gols_marcados:.1f} gols/jogo | Forma: {analise.stats_away.forma}\n"
        )
    
    h2h_txt = ""
    if analise.h2h:
        ultimos_h2h = analise.h2h[:3]
        resultados = []
        for jogo in ultimos_h2h:
            home = jogo.get("teams", {}).get("home", {}).get("name", "")
            away = jogo.get("teams", {}).get("away", {}).get("name", "")
            gols_home = jogo.get("goals", {}).get("home", 0)
            gols_away = jogo.get("goals", {}).get("away", 0)
            resultados.append(f"{home} {gols_home}x{gols_away} {away}")
        h2h_txt = f"\n🔄 <b>Últimos H2H:</b>\n  " + "\n  ".join(resultados) + "\n"
    
    mercados_txt = "\n".join([f"  • {m}" for m in analise.mercados_interessantes[:4]]) if analise.mercados_interessantes else "  • Dados insuficientes"
    
    txt = (
        f"⚽ <b>ANÁLISE PROFISSIONAL - VALOR ENCONTRADO</b>\n\n"
        f"🏆 <b>{analise.liga}</b>\n"
        f"⚔️ <b>Jogo:</b> {analise.home_team} x {analise.away_team}\n"
        f"⏰ <b>Horário:</b> {analise.horario_br.strftime('%d/%m %H:%M')}\n"
        f"{stats_txt}"
        f"{h2h_txt}\n"
        f"🎯 <b>Mercado Principal:</b> {analise.mercado_nome}\n"
        f"👉 <b>Entrada:</b> {analise.selecao_nome}\n"
        f"🏛️ <b>Casa:</b> {analise.nome_bookie.upper()}\n"
        f"📈 <b>Odd:</b> {analise.odd_bookie:.2f} (Pinnacle: {analise.odd_pinnacle:.2f})\n"
        f"📊 <b>EV:</b> +{analise.ev_real*100:.1f}% | <b>Prob Real:</b> {analise.prob_justa*100:.1f}%\n\n"
        f"💡 <b>Mercados Interessantes:</b>\n{mercados_txt}\n\n"
        f"✅ <b>Melhor Entrada:</b> {analise.selecao_nome} @ {analise.odd_bookie:.2f}\n"
        f"{analise.nivel_confianca} <b>Nível de Confiança</b>\n\n"
        f"⚠️ Aposte com responsabilidade. Análise baseada em probabilidade e estatística."
    )
    
    payload = {
        "chat_id": CHAT_ID,
        "text": txt,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        await session.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro Telegram: {e}")

# ==========================================
# REQUISIÇÕES COM FAILOVER AUTOMÁTICO
# ==========================================

def get_proxima_chave_valida():
    """Retorna a próxima chave que não está na lista de falhas"""
    global chave_odds_atual
    tentativas = 0
    while tentativas < len(API_KEYS_ODDS):
        chave = API_KEYS_ODDS[chave_odds_atual]
        if chave not in chaves_falhas:
            return chave
        chave_odds_atual = (chave_odds_atual + 1) % len(API_KEYS_ODDS)
        tentativas += 1
    return None  # Todas as chaves falharam

async def fazer_requisicao_odds(session, url, parametros):
    global chave_odds_atual, chaves_falhas
    
    # Reset chaves falhas a cada hora (tentar novamente)
    if len(chaves_falhas) >= len(API_KEYS_ODDS) - 2:
        chaves_falhas.clear()
        print("🔄 Resetando chaves falhas após 1 hora")
    
    for tentativa in range(len(API_KEYS_ODDS) * 2):  # Tentar cada chave 2x
        await rate_limit()
        
        async with api_lock:
            chave = get_proxima_chave_valida()
            if not chave:
                print("❌ Todas as chaves da API falharam!")
                return None
            
            hoje = datetime.now().strftime("%Y%m%d")
            chave_hoje = f"{chave}_{hoje}"
            
            if request_count.get(chave_hoje, 0) >= MAX_REQ_POR_CHAVE_DIA:
                chaves_falhas.add(chave)
                chave_odds_atual = (chave_odds_atual + 1) % len(API_KEYS_ODDS)
                continue
        
        parametros["apiKey"] = chave
        
        try:
            async with session.get(url, params=parametros, timeout=15) as r:
                async with api_lock:
                    request_count[chave_hoje] = request_count.get(chave_hoje, 0) + 1
                
                if r.status == 200:
                    return await r.json()
                elif r.status in [401, 429]:
                    print(f"⚠️ Chave {chave[:8]}... falhou com status {r.status}")
                    async with api_lock:
                        chaves_falhas.add(chave)
                        chave_odds_atual = (chave_odds_atual + 1) % len(API_KEYS_ODDS)
                else:
                    return await r.json()
        except asyncio.TimeoutError:
            print(f"⏱️ Timeout na chave {chave[:8]}...")
            continue
        except Exception as e:
            print(f"Erro req: {e}")
            continue
    
    return None

def validar_futebol(odd, ev, liga):
    if not (1.40 <= odd <= 10.0):
        return False
    if ev > 0.20:
        return False
    min_ev = 0.015 if LEAGUE_TIERS.get(liga, 1.0) >= 1.2 else 0.025
    return ev >= min_ev

# ==========================================
# PROCESSAMENTO
# ==========================================

async def processar_liga_async(session, liga_key, agora_br):
    parametros = {
        "regions": "eu",
        "markets": "h2h,btts,totals",
        "bookmakers": ",".join(TODAS_CASAS)
    }
    
    data = await fazer_requisicao_odds(
        session,
        f"https://api.the-odds-api.com/v4/sports/{liga_key}/odds/",
        parametros
    )
    
    if not isinstance(data, list):
        return
    
    for evento in data:
        jogo_id = str(evento["id"])
        if jogo_id in jogos_enviados:
            continue
        
        horario_br = datetime.fromisoformat(
            evento["commence_time"].replace("Z", "+00:00")
        ).astimezone(ZoneInfo("America/Sao_Paulo"))
        
        minutos = (horario_br - agora_br).total_seconds() / 60
        if not (30 <= minutos <= 1440):
            continue
        
        bookmakers = evento.get("bookmakers", [])
        pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)
        if not pinnacle:
            continue
        
        # Simplificado: sem busca externa de stats para economizar API
        stats_home, stats_away, h2h = None, None, []
        
        oportunidades = []
        
        for soft in bookmakers:
            if soft["key"] not in SOFT_BOOKIES:
                continue
            
            for m_key in ["h2h", "btts", "totals"]:
                pin_m = next((m for m in pinnacle.get("markets", []) if m["key"] == m_key), None)
                soft_m = next((m for m in soft.get("markets", []) if m["key"] == m_key), None)
                
                if pin_m and soft_m:
                    margem = sum(1/out["price"] for out in pin_m["outcomes"] if out["price"] > 0)
                    if margem <= 0:
                        continue
                    
                    for s_out in soft_m["outcomes"]:
                        p_match = next(
                            (p for p in pin_m["outcomes"]
                             if normalizar_nome(p["name"]) == normalizar_nome(s_out["name"])
                             and p.get("point") == s_out.get("point")),
                            None
                        )
                        
                        if p_match:
                            prob_real = (1 / p_match["price"]) / margem
                            ev = (prob_real * s_out["price"]) - 1
                            
                            if validar_futebol(s_out["price"], ev, liga_key):
                                score = ev * LEAGUE_TIERS.get(liga_key, 1.0)
                                
                                nivel = calcular_nivel_confianca(ev, LEAGUE_TIERS.get(liga_key, 1.0), stats_home, stats_away)
                                mercados = []
                                
                                oportunidades.append({
                                    "jogo_id": jogo_id, "evento": evento,
                                    "home_team": evento["home_team"], "away_team": evento["away_team"],
                                    "horario_br": horario_br, "mercado_nome": m_key.upper(),
                                    "selecao_nome": f"{s_out['name']} {s_out.get('point','')}",
                                    "odd_bookie": s_out["price"], "odd_pinnacle": p_match["price"],
                                    "prob_justa": prob_real, "ev_real": ev,
                                    "nome_bookie": soft["title"], "ranking_score": score,
                                    "stats_home": stats_home, "stats_away": stats_away,
                                    "h2h": h2h, "nivel_confianca": nivel,
                                    "mercados_interessantes": mercados
                                })
        
        if oportunidades:
            melhor = max(oportunidades, key=lambda x: x["ranking_score"])
            
            mercado_nome = (
                "Vencedor (1X2)" if melhor["mercado_nome"] == "H2H"
                else "Ambas Marcam" if melhor["mercado_nome"] == "BTTS"
                else "Gols Mais/Menos"
            )
            
            analise = AnaliseJogo(
                jogo_id=melhor["jogo_id"],
                home_team=melhor["home_team"],
                away_team=melhor["away_team"],
                liga=melhor["evento"]["sport_title"],
                horario_br=melhor["horario_br"],
                stats_home=melhor["stats_home"],
                stats_away=melhor["stats_away"],
                h2h=melhor["h2h"],
                mercado_nome=mercado_nome,
                selecao_nome=melhor["selecao_nome"].replace("Yes", "Sim").replace("No", "Não"),
                odd_bookie=melhor["odd_bookie"],
                odd_pinnacle=melhor["odd_pinnacle"],
                nome_bookie=melhor["nome_bookie"],
                prob_justa=melhor["prob_justa"],
                ev_real=melhor["ev_real"],
                ranking_score=melhor["ranking_score"],
                nivel_confianca=melhor["nivel_confianca"],
                melhor_entrada=f"{melhor['selecao_nome']} @ {melhor['odd_bookie']:.2f}",
                mercados_interessantes=melhor["mercados_interessantes"]
            )
            
            await enviar_telegram_async(session, analise)
            jogos_enviados[jogo_id] = agora_br + timedelta(hours=24)
            salvar_aposta_banco(melhor, 1.5, analise)

# ==========================================
# LOOP
# ==========================================

async def loop_infinito():
    while True:
        async with aiohttp.ClientSession() as session:
            agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
            print(f"⚽ Varredura Futebol: {agora_br.strftime('%H:%M')}")
            
            for i in range(0, len(LIGAS), 3):
                batch = LIGAS[i:i+3]
                await asyncio.gather(*[processar_liga_async(session, liga, agora_br) for liga in batch])
                await asyncio.sleep(5)
            
            hoje = datetime.now().strftime("%Y%m%d")
            total_req = sum(1 for k in request_count.keys() if k.endswith(f"_{hoje}"))
            print(f"📊 Requisições hoje: ~{total_req}")
        
        await asyncio.sleep(SCAN_INTERVAL)

# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    carregar_memoria_banco()
    asyncio.run(loop_infinito())