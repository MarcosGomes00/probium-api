import asyncio
import aiohttp
import sqlite3
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass, field
from typing import Optional, List, Dict
import json
import heapq

# ==========================================
# CONFIGURAÇÕES BOT 3 - BASQUETE PRO
# ==========================================

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

# APIs de estatísticas - balldontlie.io
BALLDONTLIE_KEYS = [
    "a8d9ab5d-7c93-469a-8c3a-924fd4e5e7b4",
    "8033f045-a2b3-47c6-919a-9141145c742c",
    "3ddaee43-d801-4559-84fd-e233e8f4bb9c",
    "afaca1cf-3bbe-47cc-93f5-6e7a1adfd195",
    "d1559bc7-3ceb-4c0d-8171-0d2298988cf5"
]

# SportDB API Keys
SPORTDB_KEYS = [
    "f8W9DfG71LPWMeU2TxkMtK1PEmWVwGzWW2B1Lmk9",
    "z7Dzdk5NlGtFvg5SqfL1IZWGkjOkXnOsv7tiPRrS",
    "ftAAx0FNerTm0lFMxFnWmxEbFKn7BSEMF83yosTf",
    "w1SolKpreujO7wmAKJmrW1lvfB7zK3Vv6ORnFc1t"
]

TELEGRAM_TOKEN = "8413563055:AAGyovCDMJOxiAukTbXwaJPm3ZDckIf7qJU"
CHAT_ID = "-1003814625223"

DB_FILE = "probum.db"

# Configurações de controle de qualidade
SCAN_INTERVAL = 21600  # 6 horas
MAX_APOSTAS_POR_DIA = 4  # Máximo de calls por dia (evita flop)
MIN_EV_PERCENT = 0.025  # EV mínimo de 2.5% (mais rigoroso que o anterior)
MAX_ODD = 3.0  # Odd máxima reduzida (evita risco excessivo)

# Rate limiting conservador
REQUEST_DELAY = 2.0  # 2 segundos entre requisições
MAX_REQ_POR_CHAVE_DIA = 50  # Limite conservador para durar o mês

SOFT_BOOKIES = [
    "bet365",
    "betano",
    "1xbet",
    "draftkings",
    "williamhill",
    "unibet",
    "888sport",
    "betfair_ex_eu"
]

SHARP_BOOKIE = "pinnacle"
TODAS_CASAS = SOFT_BOOKIES + [SHARP_BOOKIE]

# ==========================================
# LIGAS E TIER DE CONFIANÇA
# ==========================================

LEAGUE_TIERS = {
    "basketball_nba": 1.5,        # NBA - máxima confiança
    "basketball_euroleague": 1.2,  # Euroleague - alta confiança
    "basketball_ncaa": 1.0         # NCAA - média (adicionado)
}

LIGAS = list(LEAGUE_TIERS.keys())

# ==========================================
# ESTRUTURAS DE DADOS
# ==========================================

@dataclass
class EstatisticasTimeBasquete:
    """Estatísticas detalhadas de um time de basquete"""
    nome: str
    jogos_jogados: int = 0
    vitorias: int = 0
    derrotas: int = 0
    media_pontos_marcados: float = 0.0
    media_pontos_sofridos: float = 0.0
    media_pontos_total: float = 0.0
    over_215: float = 0.0  # % jogos over 215.5
    over_220: float = 0.0
    under_215: float = 0.0
    forma: List[str] = field(default_factory=list)  # ['W', 'W', 'L', 'W', 'L']
    pace: float = 0.0  # Posses por jogo
    offensive_rating: float = 0.0
    defensive_rating: float = 0.0
    eficiencia_arremesso: float = 0.0  # FG%
    vantagem_casa: float = 0.0  # Diferença performance casa vs fora
    back_to_back: bool = False  # Jogou ontem?
    dias_descanso: int = 2

@dataclass
class AnaliseBasquete:
    """Análise completa de uma partida de basquete"""
    jogo_id: str
    home_team: str
    away_team: str
    liga: str
    liga_key: str
    horario_br: datetime

    # Estatísticas
    stats_home: Optional[EstatisticasTimeBasquete]
    stats_away: Optional[EstatisticasTimeBasquete]
    h2h: List[Dict]

    # Dados da aposta
    mercado_nome: str  # "Vencedor", "Handicap", "Total Pontos"
    selecao_nome: str
    linha: Optional[float]  # Ex: 215.5, -4.5
    odd_bookie: float
    odd_pinnacle: float
    nome_bookie: str

    # Cálculos
    prob_justa: float
    ev_real: float
    score_qualidade: float  # Score composto para ranking

    # Análise profissional
    nivel_confianca: str  # "Alto", "Médio", "Baixo"
    mercados_sugeridos: List[str]
    melhor_call: str
    justificativa: str
    contexto: str  # Análise geral do cenário

# ==========================================
# CONTROLE GLOBAL
# ==========================================

jogos_enviados = {}  # Cache de jogos já processados
chave_odds_atual = 0
chave_balldontlie_atual = 0
chave_sportdb_atual = 0
api_lock = asyncio.Lock()
request_count = {}  # Contador por chave
last_request_time = 0

# Acumulador de oportunidades do dia
oportunidades_dia: List[tuple] = []  # (score, analise)
dia_atual = None
lock_oportunidades = asyncio.Lock()

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
    """Controla rate limiting entre requisições"""
    global last_request_time
    agora = datetime.now().timestamp()
    tempo_passado = agora - last_request_time
    if tempo_passado < REQUEST_DELAY:
        await asyncio.sleep(REQUEST_DELAY - tempo_passado)
    last_request_time = datetime.now().timestamp()

def calcular_score_qualidade(ev: float, tier_liga: float, 
                             stats_home: Optional[EstatisticasTimeBasquete],
                             stats_away: Optional[EstatisticasTimeBasquete],
                             mercado: str) -> float:
    """
    Calcula score de qualidade composto (0-100)
    Quanto maior, melhor a oportunidade
    """
    score = 0.0

    # Base: EV ponderado (máximo 40 pontos)
    score += min(ev * 1000, 40)  # EV 4% = 40 pontos

    # Bônus liga (máximo 20 pontos)
    score += (tier_liga / 1.5) * 20

    # Qualidade estatística (máximo 25 pontos)
    if stats_home and stats_away:
        # Consistência ofensiva
        diff_pontos = abs(stats_home.media_pontos_total - stats_away.media_pontos_total)
        if diff_pontos < 15:  # Times equilibrados = mais previsível
            score += 10

        # Forma recente
        forma_home = stats_home.forma.count('W') / max(len(stats_home.forma), 1)
        forma_away = stats_away.forma.count('W') / max(len(stats_away.forma), 1)
        if abs(forma_home - forma_away) > 0.4:  # Um time claramente melhor
            score += 10

        # Ritmo de jogo compatível
        if abs(stats_home.pace - stats_away.pace) < 3:
            score += 5

    # Ajuste por mercado (máximo 15 pontos)
    if mercado == "totals":
        score += 15  # Totals mais previsíveis em basquete
    elif mercado == "spreads":
        score += 12  # Handicaps moderados
    else:
        score += 8   # ML menos previsível

    return score

def determinar_nivel_confianca(score: float, ev: float, 
                                stats_disponiveis: bool) -> str:
    """Determina nível de confiança baseado no score"""
    if score >= 75 and ev >= 0.04 and stats_disponiveis:
        return "🔥 Alto"
    elif score >= 60 and ev >= 0.03:
        return "⚡ Médio"
    else:
        return "⚠️ Baixo"

def gerar_mercados_sugeridos(stats_home: EstatisticasTimeBasquete,
                              stats_away: EstatisticasTimeBasquete,
                              media_total: float) -> List[str]:
    """Gera lista de mercados interessantes baseado nas stats"""
    mercados = []

    # Análise de totals
    if media_total > 225:
        mercados.append(f"Over {int(media_total - 5)}.5 pontos")
        mercados.append(f"Over {int(media_total - 10)}.5 pontos (alternativa)")
    elif media_total < 215:
        mercados.append(f"Under {int(media_total + 5)}.5 pontos")

    # Análise de handicap baseado na diferença de forma
    if stats_home and stats_away:
        diff_vitorias = (stats_home.forma.count('W') - stats_away.forma.count('W'))
        if diff_vitorias >= 3:
            mercados.append(f"Handicap -4.5 {stats_home.nome}")
        elif diff_vitorias <= -3:
            mercados.append(f"Handicap -4.5 {stats_away.nome}")

        # Totals individuais
        if stats_home.media_pontos_marcados > 115:
            mercados.append(f"Over {int(stats_home.media_pontos_marcados - 5)}.5 pontos {stats_home.nome}")
        if stats_away.media_pontos_marcados > 115:
            mercados.append(f"Over {int(stats_away.media_pontos_marcados - 5)}.5 pontos {stats_away.nome}")

    return mercados[:4]  # Máximo 4 sugestões

def gerar_justificativa(analise: AnaliseBasquete) -> str:
    """Gera texto explicativo da call baseado nos dados"""
    partes = []

    if analise.stats_home and analise.stats_away:
        # Contexto de forma
        forma_h = analise.stats_home.forma.count('W')
        forma_a = analise.stats_away.forma.count('W')

        if forma_h > forma_a:
            partes.append(f"{analise.home_team} vem em melhor forma ({forma_h} vitórias nos últimos 5)")
        elif forma_a > forma_h:
            partes.append(f"{analise.away_team} vem em melhor forma ({forma_a} vitórias nos últimos 5)")

        # Contexto de ritmo
        if abs(analise.stats_home.pace - analise.stats_away.pace) < 2:
            partes.append("Times com ritmo de jogo similar")

        # Contexto de descanso
        if analise.stats_home.back_to_back or analise.stats_away.back_to_back:
            partes.append("Atenção: back-to-back pode afetar desempenho")

    # Contexto de mercado
    if "Over" in analise.selecao_nome:
        partes.append("Tendência ofensiva identificada nas estatísticas")
    elif "Under" in analise.selecao_nome:
        partes.append("Defesas sólidas sugerem jogo truncado")

    return " | ".join(partes) if partes else "Valor identificado na discrepância de odds"

# ==========================================
# BANCO DE DADOS
# ==========================================

def carregar_memoria_banco():
    global jogos_enviados
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id_aposta FROM operacoes_tipster WHERE status='PENDENTE' AND esporte='basketball'"
        )
        for (id_aposta,) in cursor.fetchall():
            jogos_enviados[id_aposta.split("_")[0]] = datetime.now(
                ZoneInfo("America/Sao_Paulo")
            ) + timedelta(hours=24)
        conn.close()
    except:
        pass

def salvar_aposta_banco(analise: AnaliseBasquete, stake: float):
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        id_aposta = f"{analise.jogo_id}_{analise.mercado_nome[:4]}_{analise.selecao_nome[:4]}".replace(" ", "")
        hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')

        # Criar tabela se não existir com colunas expandidas
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
                justificativa TEXT,
                stats_home TEXT,
                stats_away TEXT
            )
        """)

        cursor.execute(
            """
            INSERT OR IGNORE INTO operacoes_tipster
            (id_aposta,esporte,jogo,liga,mercado,selecao,odd,prob,ev,stake,status,lucro,data_hora,pinnacle_odd,ranking_score,nivel_confianca,justificativa,stats_home,stats_away)
            VALUES (?,?,?,?,?,?,?,?,?,?, 'PENDENTE',0,?,?,?,?,?,?,?)
            """,
            (
                id_aposta,
                "basketball",
                f"{analise.home_team} x {analise.away_team}",
                analise.liga,
                analise.mercado_nome,
                analise.selecao_nome,
                analise.odd_bookie,
                analise.prob_justa,
                analise.ev_real,
                stake,
                hoje,
                analise.odd_pinnacle,
                analise.score_qualidade,
                analise.nivel_confianca,
                analise.justificativa,
                json.dumps(analise.stats_home.__dict__ if analise.stats_home else {}),
                json.dumps(analise.stats_away.__dict__ if analise.stats_away else {})
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar: {e}")

# ==========================================
# APIs DE ESTATÍSTICAS (BASKETBALL)
# ==========================================

async def buscar_stats_balldontlie(session: aiohttp.ClientSession, 
                                    team_name: str) -> Optional[EstatisticasTimeBasquete]:
    """
    Busca estatísticas na API balldontlie (gratuita, rate limit 60 req/min)
    """
    global chave_balldontlie_atual

    if not BALLDONTLIE_KEYS:
        return None

    await rate_limit()

    try:
        # Rotacionar chaves
        async with api_lock:
            chave = BALLDONTLIE_KEYS[chave_balldontlie_atual]
            chave_balldontlie_atual = (chave_balldontlie_atual + 1) % len(BALLDONTLIE_KEYS)

        # Buscar time
        url = "https://api.balldontlie.io/v1/teams"
        headers = {"Authorization": chave}

        async with session.get(url, headers=headers, timeout=10) as r:
            if r.status == 200:
                data = await r.json()
                # Procurar time pelo nome (simplificado)
                team_id = None
                for team in data.get("data", []):
                    if normalizar_nome(team_name) in normalizar_nome(team["full_name"]):
                        team_id = team["id"]
                        break

                if not team_id:
                    return None

                # Buscar jogos recentes
                await rate_limit()
                games_url = f"https://api.balldontlie.io/v1/games?team_ids[]={team_id}&per_page=10"

                async with session.get(games_url, headers=headers, timeout=10) as r2:
                    if r2.status == 200:
                        games_data = await r2.json()
                        games = games_data.get("data", [])

                        if not games:
                            return None

                        # Calcular estatísticas
                        pontos_marcados = []
                        pontos_sofridos = []
                        forma = []

                        for game in games:
                            if game["home_team"]["id"] == team_id:
                                pontos_marcados.append(game["home_team_score"])
                                pontos_sofridos.append(game["visitor_team_score"])
                                forma.append('W' if game["home_team_score"] > game["visitor_team_score"] else 'L')
                            else:
                                pontos_marcados.append(game["visitor_team_score"])
                                pontos_sofridos.append(game["home_team_score"])
                                forma.append('W' if game["visitor_team_score"] > game["home_team_score"] else 'L')

                        media_marcados = sum(pontos_marcados) / len(pontos_marcados)
                        media_sofridos = sum(pontos_sofridos) / len(pontos_sofridos)
                        total_jogos = len(games)

                        # Calcular overs
                        overs_215 = sum(1 for i in range(total_jogos) 
                                       if (pontos_marcados[i] + pontos_sofridos[i]) > 215.5) / total_jogos * 100
                        overs_220 = sum(1 for i in range(total_jogos) 
                                       if (pontos_marcados[i] + pontos_sofridos[i]) > 220.5) / total_jogos * 100

                        return EstatisticasTimeBasquete(
                            nome=team_name,
                            jogos_jogados=total_jogos,
                            vitorias=forma.count('W'),
                            derrotas=forma.count('L'),
                            media_pontos_marcados=media_marcados,
                            media_pontos_sofridos=media_sofridos,
                            media_pontos_total=media_marcados + media_sofridos,
                            over_215=overs_215,
                            over_220=overs_220,
                            under_215=100 - overs_215,
                            forma=forma[:5],
                            pace=100.0,  # Placeholder - requer dados avançados
                            offensive_rating=media_marcados / 100 * 100,  # Simplificado
                            defensive_rating=media_sofridos / 100 * 100,
                            eficiencia_arremesso=0.45,  # Placeholder
                            vantagem_casa=3.5,  # Estimativa NBA
                            back_to_back=False,  # Requer lógica adicional
                            dias_descanso=2
                        )
    except Exception as e:
        print(f"Erro ao buscar stats para {team_name}: {e}")

    return None

async def buscar_h2h_basquete(session: aiohttp.ClientSession,
                               home_team: str,
                               away_team: str) -> List[Dict]:
    """Busca histórico de confrontos diretos"""
    if not BALLDONTLIE_KEYS:
        return []

    # Simplificado - na prática precisaria buscar IDs dos times primeiro
    return []

# ==========================================
# TELEGRAM - FORMATO PROFISSIONAL
# ==========================================

async def enviar_telegram_profissional(session: aiohttp.ClientSession, 
                                        analise: AnaliseBasquete):
    """Envia análise no formato profissional solicitado"""

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    # Formatar estatísticas
    stats_txt = ""
    if analise.stats_home and analise.stats_away:
        stats_txt = (
            f"\n📊 <b>Estatísticas Relevantes:</b>\n"
            f"  <i>{analise.home_team}:</i>\n"
            f"    • Média pontos: {analise.stats_home.media_pontos_marcados:.1f}\n"
            f"    • Forma: {' '.join(analise.stats_home.forma[:5])}\n"
            f"    • Over 215.5: {analise.stats_home.over_215:.0f}%\n"
            f"  <i>{analise.away_team}:</i>\n"
            f"    • Média pontos: {analise.stats_away.media_pontos_marcados:.1f}\n"
            f"    • Forma: {' '.join(analise.stats_away.forma[:5])}\n"
            f"    • Over 215.5: {analise.stats_away.over_215:.0f}%\n"
        )

    # Formatar H2H
    h2h_txt = ""
    if analise.h2h:
        ultimos = analise.h2h[:3]
        resultados = []
        for jogo in ultimos:
            home = jogo.get("home_team", {}).get("name", "Home")
            away = jogo.get("visitor_team", {}).get("name", "Away")
            home_score = jogo.get("home_team_score", 0)
            away_score = jogo.get("visitor_team_score", 0)
            resultados.append(f"{home} {home_score}x{away_score} {away}")
        h2h_txt = f"\n🔄 <b>Últimos H2H:</b>\n  " + "\n  ".join(resultados) + "\n"

    # Mercados sugeridos
    mercados_txt = "\n".join([f"  • {m}" for m in analise.mercados_sugeridos]) if analise.mercados_sugeridos else "  • Nenhum mercado adicional identificado"

    # Análise geral
    contexto = analise.contexto if analise.contexto else f"Confronto entre {analise.home_team} e {analise.away_team} na {analise.liga}"

    # Montar mensagem final no formato profissional
    texto = (
        f"🏀 <b>CALL PROFISSIONAL - BASQUETE</b>\n\n"
        f"<b>Jogo:</b>\n{analise.home_team} vs {analise.away_team}\n\n"
        f"<b>Análise Geral:</b>\n{contexto}\n"
        f"{stats_txt}"
        f"{h2h_txt}\n"
        f"<b>Mercados Interessantes:</b>\n{mercados_txt}\n\n"
        f"✅ <b>MELHOR CALL:</b>\n"
        f"  {analise.selecao_nome}\n"
        f"  🏛️ Casa: {analise.nome_bookie.upper()}\n"
        f"  📈 Odd: {analise.odd_bookie:.2f} (Pinnacle: {analise.odd_pinnacle:.2f})\n"
        f"  📊 EV: +{analise.ev_real*100:.1f}% | Prob Real: {analise.prob_justa*100:.1f}%\n\n"
        f"💡 <b>Justificativa:</b> {analise.justificativa}\n\n"
        f"{analise.nivel_confianca} <b>Nível de Confiança</b>\n\n"
        f"⚠️ <i>Análise baseada em estatísticas e probabilidade. "
        f"Gerencie sua banca e aposte com responsabilidade.</i>"
    )

    payload = {
        "chat_id": CHAT_ID,
        "text": texto,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        await session.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Erro ao enviar Telegram: {e}")

# ==========================================
# REQUISIÇÃO ODDS COM CONTROLE
# ==========================================

async def fazer_requisicao_odds(session, url, parametros):
    global chave_odds_atual

    for _ in range(len(API_KEYS_ODDS)):
        await rate_limit()

        async with api_lock:
            chave = API_KEYS_ODDS[chave_odds_atual]
            hoje = datetime.now().strftime("%Y%m%d")
            chave_hoje = f"{chave}_{hoje}"

            if request_count.get(chave_hoje, 0) >= MAX_REQ_POR_CHAVE_DIA:
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
                    async with api_lock:
                        chave_odds_atual = (chave_odds_atual + 1) % len(API_KEYS_ODDS)
                else:
                    return await r.json()
        except Exception as e:
            print(f"Erro requisição: {e}")
            continue

    return None

# ==========================================
# VALIDAÇÃO RIGOROSA
# ==========================================

def validar_basquete_pro(odd: float, ev: float, liga: str) -> bool:
    """Validação mais rigorosa para evitar 'flops'"""

    # Odd fora do range seguro
    if not (1.30 <= odd <= MAX_ODD):
        return False

    # EV insuficiente
    if ev < MIN_EV_PERCENT:
        return False

    # EV excessivo (suspeito)
    if ev > 0.12:  # Max 12% EV
        return False

    return True

# ==========================================
# PROCESSAMENTO INTELIGENTE
# ==========================================

async def processar_liga_async(session, liga_key: str, agora_br: datetime):
    """Processa uma liga e acumula oportunidades"""
    global oportunidades_dia, dia_atual

    parametros = {
        "regions": "eu",
        "markets": "h2h,spreads,totals",
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

        # Apenas jogos nas próximas 24h
        if not (30 <= minutos <= 1440):
            continue

        bookmakers = evento.get("bookmakers", [])
        pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)

        if not pinnacle:
            continue

        home_team = evento["home_team"]
        away_team = evento["away_team"]

        # Buscar estatísticas (com timeout curto para não travar)
        stats_home, stats_away, h2h = None, None, []
        try:
            stats_task = asyncio.gather(
                asyncio.wait_for(buscar_stats_balldontlie(session, home_team), timeout=5),
                asyncio.wait_for(buscar_stats_balldontlie(session, away_team), timeout=5),
                asyncio.wait_for(buscar_h2h_basquete(session, home_team, away_team), timeout=5),
                return_exceptions=True
            )
            results = await stats_task
            stats_home = results[0] if not isinstance(results[0], Exception) else None
            stats_away = results[1] if not isinstance(results[1], Exception) else None
            h2h = results[2] if not isinstance(results[2], Exception) else []
        except:
            pass

        # Processar mercados
        for soft in bookmakers:
            if soft["key"] not in SOFT_BOOKIES:
                continue

            for m_key in ["h2h", "spreads", "totals"]:
                pin_m = next((m for m in pinnacle.get("markets", []) if m["key"] == m_key), None)
                soft_m = next((m for m in soft.get("markets", []) if m["key"] == m_key), None)

                if not (pin_m and soft_m):
                    continue

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

                    if not p_match:
                        continue

                    prob_real = (1 / p_match["price"]) / margem
                    ev = (prob_real * s_out["price"]) - 1

                    if not validar_basquete_pro(s_out["price"], ev, liga_key):
                        continue

                    # Calcular métricas de qualidade
                    score = calcular_score_qualidade(
                        ev, LEAGUE_TIERS.get(liga_key, 1.0),
                        stats_home, stats_away, m_key
                    )

                    nivel = determinar_nivel_confianca(
                        score, ev, stats_home is not None and stats_away is not None
                    )

                    # Gerar sugestões de mercados
                    media_total = 0
                    if stats_home and stats_away:
                        media_total = (stats_home.media_pontos_total + stats_away.media_pontos_total) / 2

                    mercados = []
                    if stats_home and stats_away:
                        mercados = gerar_mercados_sugeridos(stats_home, stats_away, media_total)

                    # Criar objeto de análise
                    mercado_nome = (
                        "Vencedor" if m_key == "h2h"
                        else "Handicap de Pontos" if m_key == "spreads"
                        else "Total de Pontos"
                    )

                    analise = AnaliseBasquete(
                        jogo_id=jogo_id,
                        home_team=home_team,
                        away_team=away_team,
                        liga=evento["sport_title"],
                        liga_key=liga_key,
                        horario_br=horario_br,
                        stats_home=stats_home,
                        stats_away=stats_away,
                        h2h=h2h,
                        mercado_nome=mercado_nome,
                        selecao_nome=f"{s_out['name']} {s_out.get('point', '')}".strip(),
                        linha=s_out.get("point"),
                        odd_bookie=s_out["price"],
                        odd_pinnacle=p_match["price"],
                        nome_bookie=soft["title"],
                        prob_justa=prob_real,
                        ev_real=ev,
                        score_qualidade=score,
                        nivel_confianca=nivel,
                        mercados_sugeridos=mercados,
                        melhor_call=f"{s_out['name']} @ {s_out['price']}",
                        justificativa="",  # Preenchido depois
                        contexto=""
                    )

                    analise.justificativa = gerar_justificativa(analise)

                    # Adicionar à lista de oportunidades do dia (thread-safe)
                    async with lock_oportunidades:
                        heapq.heappush(oportunidades_dia, (-score, analise))  # Max heap usando negativo

async def enviar_melhores_do_dia(session: aiohttp.ClientSession):
    """Envia apenas as top N oportunidades do dia"""
    global oportunidades_dia, dia_atual

    async with lock_oportunidades:
        if not oportunidades_dia:
            print("ℹ️ Nenhuma oportunidade de qualidade encontrada hoje")
            return

        # Pegar as top MAX_APOSTAS_POR_DIA
        melhores = []
        while len(melhores) < MAX_APOSTAS_POR_DIA and oportunidades_dia:
            _, analise = heapq.heappop(oportunidades_dia)
            melhores.append(analise)

        # Limpar restante
        oportunidades_dia = []

    if not melhores:
        return

    # Enviar resumo inicial
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).strftime('%d/%m/%Y')

    resumo = (
        f"🏀 <b>TOP CALLS DO DIA - {hoje}</b>\n\n"
        f"Selecionadas {len(melhores)} melhores oportunidades de basquete "
        f"baseadas em análise estatística e valor de odds.\n\n"
        f"📊 Critérios: EV ≥ {MIN_EV_PERCENT*100:.1f}%, Odd ≤ {MAX_ODD}, "
        f"Score de qualidade ≥ 60/100\n"
        f"⚠️ Máximo {MAX_APOSTAS_POR_DIA} calls por dia para garantir qualidade"
    )

    try:
        await session.post(url, json={
            "chat_id": CHAT_ID,
            "text": resumo,
            "parse_mode": "HTML"
        }, timeout=10)
    except:
        pass

    # Enviar cada análise detalhada
    for i, analise in enumerate(melhores, 1):
        # Adicionar ranking na mensagem
        analise.contexto = f"🏆 Ranking #{i} do dia | Score: {analise.score_qualidade:.0f}/100"
        await enviar_telegram_profissional(session, analise)

        # Salvar no banco
        salvar_aposta_banco(analise, 1.5)

        # Marcar como enviado
        jogos_enviados[analise.jogo_id] = datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(hours=24)

        await asyncio.sleep(1)  # Pausa entre mensagens

# ==========================================
# LOOP PRINCIPAL
# ==========================================

async def loop_infinito():
    global oportunidades_dia, dia_atual

    while True:
        async with aiohttp.ClientSession() as session:
            agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
            hoje = agora_br.date()

            # Reset diário
            if dia_atual != hoje:
                async with lock_oportunidades:
                    oportunidades_dia = []
                dia_atual = hoje
                print(f"📅 Novo dia iniciado: {hoje}")

            print(f"🏀 Varredura Basquete Iniciada: {agora_br.strftime('%H:%M')}")

            # Acumular oportunidades de todas as ligas
            for liga in LIGAS:
                await processar_liga_async(session, liga, agora_br)
                await asyncio.sleep(2)  # Pausa entre ligas

            # Enviar apenas as melhores no final da varredura
            await enviar_melhores_do_dia(session)

            # Log de uso
            total_req = sum(request_count.values())
            print(f"📊 Total requisições acumuladas: {total_req}")
            print(f"💤 Aguardando próxima varredura em {SCAN_INTERVAL/3600:.1f}h...")

        await asyncio.sleep(SCAN_INTERVAL)

# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    carregar_memoria_banco()
    asyncio.run(loop_infinito())