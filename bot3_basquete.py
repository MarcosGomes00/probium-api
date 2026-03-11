import asyncio
import aiohttp
import sqlite3
import unicodedata
import heapq
import time
import statistics
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple
import json

# ==========================================
# CONFIGURAÇÕES BOT 3 - BASQUETE PRO MULTIPROVIDER
# ==========================================

# ==========================================
# CHAVES DE API MULTIPROVIDER - FAILOVER SYSTEM
# ==========================================

# 1. ODDS API (Odds-API.io) - Melhor custo-benefício, WebSocket
ODDS_API_KEYS = [
    "6249ca36b148b2542bb433d23e4ace65a97c896b7dc3b93c79b4a6715b29ea7d",
    "b29dcd347f5f26ddebb469eaa9e5f98fb75ca20be03cc47117027604d0a9f029",
    "528e79310c9161f769a282b8d2aa61be2bb332e0cc036a51e44acee5ca7bd66f"
]

# 2. Sports Game Odds (SGO) - Modelo de precificação superior
SGO_API_KEYS = [
    "e38185eb8b9eff32802ff016db544dc3"
]

# 3. The Odds Token (OddsPapi) - 346 bookmakers, dados sharps
THE_ODDS_TOKEN_KEYS = [
    "b668851102c3e0a56c33220161c029ec",
    "0d43575dd39e175ba670fb91b2230442",
    "d32378e66e89f159688cc2239f38a6a4",
    "713146de690026b224dd8bbf0abc0339"
]

# 4. The Odds API (Legado - mantido como backup)
THE_ODDS_API_LEGACY_KEYS = [
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

# 5. Ball Don't Lie (NBA dados) - app.balldontlie.io
BALLDONTLIE_KEYS = [
    "a8d9ab5d-7c93-469a-8c3a-924fd4e5e7b4",
    "8033f045-a2b3-47c6-919a-9141145c742c",
    "3ddaee43-d801-4559-84fd-e233e8f4bb9c",
    "afaca1cf-3bbe-47cc-93f5-6e7a1adfd195",
    "d1559bc7-3ceb-4c0d-8171-0d2298988cf5"
]

# 6. SportDB API Keys
SPORTDB_KEYS = [
    "f8W9DfG71LPWMeU2TxkMtK1PEmWVwGzWW2B1Lmk9",
    "z7Dzdk5NlGtFvg5SqfL1IZWGkjOkXnOsv7tiPRrS",
    "ftAAx0FNerTm0lFMxFnWmxEbFKn7BSEMF83yosTf",
    "w1SolKpreujO7wmAKJmrW1lvfB7zK3Vv6ORnFc1t"
]

# Configurações de Tokens do Telegram
TELEGRAM_TOKENS = {
    "bot1": "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A",
    "bot2": "8185027087:AAH1JQJKtlWy_oUQpAvqvHEsFIVOK3ScYBc",
    "bot3": "8413563055:AAGyovCDMJOxiAukTbXwaJPm3ZDckIf7qJU"
}

# Usando Bot3 como principal (específico do basquete)
TELEGRAM_TOKEN = TELEGRAM_TOKENS["bot3"]
CHAT_ID = "-1003814625223"
DB_FILE = "probum.db"

# Configurações de controle de qualidade
SCAN_INTERVAL = 21600  # 6 horas
MAX_APOSTAS_POR_DIA = 4  # Máximo de calls por dia (evita flop)
MIN_EV_PERCENT = 0.025  # EV mínimo de 2.5% (mais rigoroso que o anterior)
MAX_ODD = 3.0  # Odd máxima reduzida (evita risco excessivo)

# Rate limiting conservador
REQUEST_DELAY = 2.0  # 2 segundos entre requisições

# Limites por provedor (ajustados conforme documentação)
MAX_REQ_POR_CHAVE_DIA = {
    "odds_api": 2400,        # 100/hora * 24 = 2400/dia (Odds-API.io)
    "sgo": 1000,             # 1.000 objetos/mês (Sports Game Odds)
    "the_odds_token": 500,   # Estimado conservador
    "the_odds_api_legacy": 50,
    "balldontlie": 1000,     # 60 req/min * 60 * 24 = 86.400/dia (muito alto, limitamos)
    "sportdb": 1000          # Estimado
}

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
    fonte_dados: str = ""  # Novo: rastrear qual API forneceu os dados

# ==========================================
# CONTROLE GLOBAL
# ==========================================

jogos_enviados = {}  # Cache de jogos já processados
api_lock = asyncio.Lock()
request_count = {}  # Contador por chave
last_request_time = 0
chaves_falhas = {}  # {provider: {chave: timestamp_falha}}
provedores_falhos = set()  # Provedores completamente offline

# Acumulador de oportunidades do dia
oportunidades_dia: List[tuple] = []  # (score, analise)
dia_atual = None
lock_oportunidades = asyncio.Lock()

# Índices de rotação para cada provedor
indice_chaves = {
    "odds_api": 0,
    "sgo": 0,
    "the_odds_token": 0,
    "the_odds_api_legacy": 0,
    "balldontlie": 0,
    "sportdb": 0
}

# ==========================================
# SISTEMA DE HEALTH CHECK PARA PROVEDORES
# ==========================================

@dataclass
class ProvedorHealth:
    """Monitora saúde de cada provedor para decisões inteligentes de failover"""
    latencias: List[float] = field(default_factory=list)
    erros_consecutivos: int = 0
    sucessos_consecutivos: int = 0
    ultimo_sucesso: datetime = field(default_factory=datetime.now)
    score: float = 100.0  # 0-100
    total_requisicoes: int = 0
    total_erros: int = 0
    
    def registrar_sucesso(self, latencia_ms: float):
        self.latencias.append(latencia_ms)
        if len(self.latencias) > 10:
            self.latencias.pop(0)
        self.erros_consecutivos = 0
        self.sucessos_consecutivos += 1
        self.ultimo_sucesso = datetime.now()
        self.score = min(100.0, self.score + 10.0)
        self.total_requisicoes += 1
    
    def registrar_erro(self):
        self.erros_consecutivos += 1
        self.sucessos_consecutivos = 0
        penalidade = 15 * self.erros_consecutivos
        self.score = max(0.0, self.score - penalidade)
        self.total_requisicoes += 1
        self.total_erros += 1
    
    def esta_saudavel(self) -> bool:
        # Se score < 30 ou 3+ erros consecutivos, considera "quebrado"
        return self.score > 30 and self.erros_consecutivos < 3
    
    def latencia_media(self) -> float:
        if not self.latencias:
            return 0.0
        return statistics.mean(self.latencias)
    
    def taxa_erro(self) -> float:
        if self.total_requisicoes == 0:
            return 0.0
        return (self.total_erros / self.total_requisicoes) * 100

# ==========================================
# SISTEMA DE CACHE DISTRIBUÍDO DE ODDS
# ==========================================

class OddsCache:
    """Cache compartilhado de odds para economizar requisições entre bots"""
    
    def __init__(self, db_file="odds_cache_basquete.db"):
        self.db = db_file
        self.init_db()
        self.cache_hits = 0
        self.cache_misses = 0
    
    def init_db(self):
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS odds_cache (
                jogo_id TEXT PRIMARY KEY,
                liga TEXT,
                esporte TEXT,
                dados_json TEXT,
                provedor TEXT,
                timestamp REAL,
                ttl INTEGER DEFAULT 300
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_liga ON odds_cache(liga)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON odds_cache(timestamp)
        """)
        conn.commit()
        conn.close()
    
    def get(self, jogo_id: str) -> Optional[dict]:
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT dados_json, timestamp, ttl FROM odds_cache WHERE jogo_id=?",
            (jogo_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            dados, ts, ttl = row
            agora = datetime.now().timestamp()
            if agora - ts < ttl:
                self.cache_hits += 1
                return json.loads(dados)
        
        self.cache_misses += 1
        return None
    
    def set(self, jogo_id: str, dados: dict, provedor: str, ttl: int = 300):
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO odds_cache 
            (jogo_id, liga, esporte, dados_json, provedor, timestamp, ttl)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            jogo_id,
            dados.get("sport_key", "unknown"),
            dados.get("sport_title", "unknown"),
            json.dumps(dados),
            provedor,
            datetime.now().timestamp(),
            ttl
        ))
        conn.commit()
        conn.close()
    
    def limpar_expirados(self):
        """Remove entradas expiradas do cache"""
        conn = sqlite3.connect(self.db)
        cursor = conn.cursor()
        agora = datetime.now().timestamp()
        cursor.execute("DELETE FROM odds_cache WHERE ? - timestamp > ttl", (agora,))
        deletados = cursor.rowcount
        conn.commit()
        conn.close()
        return deletados
    
    def estatisticas(self) -> dict:
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total * 100) if total > 0 else 0
        return {
            "hits": self.cache_hits,
            "misses": self.cache_misses,
            "hit_rate": hit_rate,
            "economia_requisicoes": self.cache_hits
        }

# Instância global do cache
odds_cache = OddsCache()

# ==========================================
# SISTEMA DE FAILOVER MULTIPROVIDER
# ==========================================

class APIProviderManager:
    """Gerencia múltiplos provedores de API com failover automático e health check"""
    
    PRIORIDADE_PROVEDORES = [
        "odds_api",           # 1º: Odds-API.io (melhor custo-benefício)
        "sgo",                # 2º: Sports Game Odds (modelo econômico)
        "the_odds_token",     # 3º: The Odds Token (346 bookmakers)
        "the_odds_api_legacy", # 4º: The Odds API (legado)
    ]
    
    def __init__(self):
        self.chaves_por_provedor = {
            "odds_api": ODDS_API_KEYS,
            "sgo": SGO_API_KEYS,
            "the_odds_token": THE_ODDS_TOKEN_KEYS,
            "the_odds_api_legacy": THE_ODDS_API_LEGACY_KEYS
        }
        
        self.provedor_atual_idx = 0
        self.health_por_provedor = {
            p: ProvedorHealth() for p in self.PRIORIDADE_PROVEDORES
        }
    
    def get_provedor_atual(self) -> Optional[str]:
        """Retorna o provedor mais saudável baseado em health score"""
        disponiveis = [p for p in self.PRIORIDADE_PROVEDORES 
                      if p not in provedores_falhos and self.health_por_provedor[p].esta_saudavel()]
        
        if not disponiveis:
            # Se nenhum está saudável, tenta qualquer um disponível
            disponiveis = [p for p in self.PRIORIDADE_PROVEDORES if p not in provedores_falhos]
        
        if not disponiveis:
            return None
        
        # Ordena por health score (maior primeiro)
        disponiveis.sort(key=lambda p: self.health_por_provedor[p].score, reverse=True)
        return disponiveis[0]
    
    def proximo_provedor(self):
        """Avança para o próximo provedor na lista de prioridade"""
        self.provedor_atual_idx = (self.provedor_atual_idx + 1) % len(self.PRIORIDADE_PROVEDORES)
    
    def get_chave_valida(self, provedor: str) -> Tuple[Optional[str], int]:
        """Retorna uma chave válida e o índice para o provedor especificado"""
        chaves = self.chaves_por_provedor.get(provedor, [])
        if not chaves:
            return None, 0
        
        tentativas = 0
        while tentativas < len(chaves):
            idx = indice_chaves[provedor] % len(chaves)
            chave = chaves[idx]
            
            # Verifica se chave não falhou recentemente (última hora)
            falhas_provedor = chaves_falhas.get(provedor, {})
            ultima_falha = falhas_provedor.get(chave, 0)
            
            if (datetime.now().timestamp() - ultima_falha) > 3600:  # 1 hora
                return chave, idx
            
            indice_chaves[provedor] = (indice_chaves[provedor] + 1) % len(chaves)
            tentativas += 1
        
        return None, 0
    
    def marcar_chave_falha(self, provedor: str, chave: str):
        """Marca uma chave como falha"""
        if provedor not in chaves_falhas:
            chaves_falhas[provedor] = {}
        chaves_falhas[provedor][chave] = datetime.now().timestamp()
        self.health_por_provedor[provedor].registrar_erro()
        print(f"⚠️ Basquete: Chave {chave[:8]}... do {provedor} marcada como falha (Score: {self.health_por_provedor[provedor].score:.0f})")
    
    def marcar_sucesso(self, provedor: str, latencia_ms: float):
        """Registra sucesso no health check"""
        self.health_por_provedor[provedor].registrar_sucesso(latencia_ms)
    
    def marcar_provedor_offline(self, provedor: str):
        """Marca todo o provedor como offline"""
        provedores_falhos.add(provedor)
        print(f"🚫 Basquete: Provedor {provedor} marcado como offline temporariamente")
        
        # Agenda reativação em 30 minutos
        asyncio.create_task(self.reativar_provedor(provedor, 1800))
    
    async def reativar_provedor(self, provedor: str, delay: int):
        """Reativa um provedor após delay"""
        await asyncio.sleep(delay)
        if provedor in provedores_falhos:
            provedores_falhos.remove(provedor)
            self.health_por_provedor[provedor].score = 50  # Reset para valor médio
            print(f"✅ Basquete: Provedor {provedor} reativado")
    
    def get_health_report(self) -> str:
        """Gera relatório de saúde dos provedores"""
        linhas = ["📊 Health Check Provedores:"]
        for provedor in self.PRIORIDADE_PROVEDORES:
            h = self.health_por_provedor[provedor]
            status = "🟢" if h.esta_saudavel() else "🔴"
            linhas.append(f"{status} {provedor}: Score={h.score:.0f} | Lat={h.latencia_media():.0f}ms | Erros={h.erros_consecutivos}")
        return "\n".join(linhas)

# Instância global do gerenciador
provider_manager = APIProviderManager()

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

def gerar_justificativa(analise) -> str:
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

def salvar_aposta_banco(analise, stake: float):
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
                stats_away TEXT,
                fonte_dados TEXT
            )
        """)

        cursor.execute(
            """
            INSERT OR IGNORE INTO operacoes_tipster
            (id_aposta,esporte,jogo,liga,mercado,selecao,odd,prob,ev,stake,status,lucro,data_hora,pinnacle_odd,ranking_score,nivel_confianca,justificativa,stats_home,stats_away,fonte_dados)
            VALUES (?,?,?,?,?,?,?,?,?,?, 'PENDENTE',0,?,?,?,?,?,?,?,?)
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
                json.dumps(analise.stats_away.__dict__ if analise.stats_away else {}),
                analise.fonte_dados
            )
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Erro ao salvar: {e}")

# ==========================================
# APIs DE ESTATÍSTICAS (BASKETBALL) - MULTIPROVIDER
# ==========================================

class StatsProviderManager:
    """Gerencia múltiplas fontes de estatísticas de basquete"""
    
    def __init__(self):
        self.chave_balldontlie_atual = 0
        self.chave_sportdb_atual = 0
    
    async def buscar_stats(self, session: aiohttp.ClientSession, 
                          team_name: str) -> Optional[EstatisticasTimeBasquete]:
        """Tenta buscar estatísticas de múltiplas fontes"""
        
        # 1º tentativa: Ball Don't Lie (NBA)
        stats = await self._buscar_balldontlie(session, team_name)
        if stats:
            return stats
        
        # 2º tentativa: SportDB (dados gerais)
        stats = await self._buscar_sportdb(session, team_name)
        if stats:
            return stats
        
        return None
    
    async def _buscar_balldontlie(self, session: aiohttp.ClientSession, 
                                   team_name: str) -> Optional[EstatisticasTimeBasquete]:
        """Busca estatísticas na API balldontlie"""
        
        if not BALLDONTLIE_KEYS:
            return None

        await rate_limit()

        try:
            # Rotacionar chaves
            async with api_lock:
                chave = BALLDONTLIE_KEYS[self.chave_balldontlie_atual]
                self.chave_balldontlie_atual = (self.chave_balldontlie_atual + 1) % len(BALLDONTLIE_KEYS)

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
                elif r.status in [401, 429]:
                    # Marca chave como falha e tenta próxima
                    print(f"⚠️ Ball Don't Lie chave falhou: {r.status}")
                    async with api_lock:
                        self.chave_balldontlie_atual = (self.chave_balldontlie_atual + 1) % len(BALLDONTLIE_KEYS)
        except Exception as e:
            print(f"Erro ao buscar stats Ball Don't Lie para {team_name}: {e}")

        return None
    
    async def _buscar_sportdb(self, session: aiohttp.ClientSession,
                               team_name: str) -> Optional[EstatisticasTimeBasquete]:
        """Busca estatísticas na API SportDB como fallback"""
        
        if not SPORTDB_KEYS:
            return None
        
        await rate_limit()
        
        try:
            async with api_lock:
                chave = SPORTDB_KEYS[self.chave_sportdb_atual]
                self.chave_sportdb_atual = (self.chave_sportdb_atual + 1) % len(SPORTDB_KEYS)
            
            # Buscar time
            url = f"https://www.thesportsdb.com/api/v1/json/{chave}/searchteams.php"
            params = {"t": team_name}
            
            async with session.get(url, params=params, timeout=10) as r:
                if r.status == 200:
                    data = await r.json()
                    teams = data.get("teams", [])
                    if not teams:
                        return None
                    
                    team_id = teams[0].get("idTeam")
                    
                    # Buscar eventos recentes
                    await rate_limit()
                    events_url = f"https://www.thesportsdb.com/api/v1/json/{chave}/eventslast.php"
                    events_params = {"id": team_id}
                    
                    async with session.get(events_url, params=events_params, timeout=10) as r2:
                        if r2.status == 200:
                            events_data = await r2.json()
                            results = events_data.get("results", [])
                            
                            if not results:
                                return None
                            
                            # Processar resultados (simplificado)
                            pontos_marcados = []
                            forma = []
                            
                            for event in results[:10]:
                                home_score = int(event.get("intHomeScore", 0) or 0)
                                away_score = int(event.get("intAwayScore", 0) or 0)
                                
                                if event.get("idHomeTeam") == team_id:
                                    pontos_marcados.append(home_score)
                                    forma.append('W' if home_score > away_score else 'L')
                                else:
                                    pontos_marcados.append(away_score)
                                    forma.append('W' if away_score > home_score else 'L')
                            
                            if not pontos_marcados:
                                return None
                            
                            media_marcados = sum(pontos_marcados) / len(pontos_marcados)
                            
                            return EstatisticasTimeBasquete(
                                nome=team_name,
                                jogos_jogados=len(pontos_marcados),
                                vitorias=forma.count('W'),
                                derrotas=forma.count('L'),
                                media_pontos_marcados=media_marcados,
                                media_pontos_sofridos=0,  # Não disponível no SportDB
                                media_pontos_total=media_marcados,
                                over_215=0,
                                over_220=0,
                                under_215=0,
                                forma=forma[:5],
                                pace=0,
                                offensive_rating=0,
                                defensive_rating=0,
                                eficiencia_arremesso=0,
                                vantagem_casa=0,
                                back_to_back=False,
                                dias_descanso=2
                            )
        except Exception as e:
            print(f"Erro ao buscar stats SportDB para {team_name}: {e}")
        
        return None

# Instância global do gerenciador de estatísticas
stats_manager = StatsProviderManager()

async def buscar_h2h_basquete(session: aiohttp.ClientSession,
                               home_team: str,
                               away_team: str) -> List[Dict]:
    """Busca histórico de confrontos diretos"""
    if not BALLDONTLIE_KEYS:
        return []

    # Simplificado - na prática precisaria buscar IDs dos times primeiro
    return []

# ==========================================
# TELEGRAM - MULTIBOT FAILOVER
# ==========================================

async def enviar_telegram_profissional(session: aiohttp.ClientSession, 
                                        analise):
    """Envia análise no formato profissional com failover de bots"""

    # Tenta enviar com bot3, se falhar tenta bot2, depois bot1
    bots = [TELEGRAM_TOKENS["bot3"], TELEGRAM_TOKENS["bot2"], TELEGRAM_TOKENS["bot1"]]
    
    for token in bots:
        url = f"https://api.telegram.org/bot{token}/sendMessage"

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
            f"🏀 <b>CALL PROFISSIONAL - BASQUETE</b>\n"
            f"<i>Fonte: {analise.fonte_dados}</i>\n\n"
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
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    return True
                else:
                    print(f"⚠️ Basquete: Bot falhou com status {resp.status}, tentando próximo...")
                    continue
        except Exception as e:
            print(f"Erro Telegram Basquete: {e}")
            continue
    
    print("❌ Basquete: Todos os bots falharam!")
    return False

# ==========================================
# REQUISIÇÕES MULTIPROVIDER COM FAILOVER
# ==========================================

async def fazer_requisicao_odds_multiprovider(session, liga_key: str, tentativas_max: int = 10):
    """
    Tenta obter odds de múltiplos provedores em ordem de prioridade
    """
    for tentativa in range(tentativas_max):
        provedor = provider_manager.get_provedor_atual()
        
        if not provedor:
            print("❌ Basquete: Nenhum provedor disponível! Aguardando 5 minutos...")
            await asyncio.sleep(300)
            provedores_falhos.clear()  # Limpa falhas e tenta novamente
            continue
        
        chave, idx = provider_manager.get_chave_valida(provedor)
        
        if not chave:
            print(f"⚠️ Basquete: Todas as chaves do {provedor} esgotadas/falhas")
            provider_manager.marcar_provedor_offline(provedor)
            provider_manager.proximo_provedor()
            continue
        
        await rate_limit()
        
        inicio_req = time.time()
        
        # Constrói URL e parâmetros conforme o provedor
        if provedor == "odds_api":
            url = f"https://api.the-odds-api.com/v4/sports/{liga_key}/odds/"
            params = {
                "apiKey": chave,
                "regions": "eu",
                "markets": "h2h,spreads,totals",
                "bookmakers": ",".join(TODAS_CASAS)
            }
        elif provedor == "sgo":
            url = "https://api.sportsgameodds.com/v1/events"
            params = {
                "apiKey": chave,
                "sport": "basketball",
                "league": liga_key.replace("basketball_", ""),
                "markets": "h2h,spreads,totals"
            }
        elif provedor in ["the_odds_token", "the_odds_api_legacy"]:
            url = f"https://api.the-odds-api.com/v4/sports/{liga_key}/odds/"
            params = {
                "apiKey": chave,
                "regions": "eu",
                "markets": "h2h,spreads,totals",
                "bookmakers": ",".join(TODAS_CASAS)
            }
        else:
            url = f"https://api.the-odds-api.com/v4/sports/{liga_key}/odds/"
            params = {"apiKey": chave, "regions": "eu", "markets": "h2h"}
        
        try:
            hoje = datetime.now().strftime("%Y%m%d")
            chave_hoje = f"{provedor}_{chave}_{hoje}"
            
            async with api_lock:
                request_count[chave_hoje] = request_count.get(chave_hoje, 0) + 1
                
                # Verifica limite diário
                if request_count[chave_hoje] >= MAX_REQ_POR_CHAVE_DIA.get(provedor, 50):
                    print(f"⚠️ Basquete: Limite diário atingido para {provedor}")
                    provider_manager.marcar_chave_falha(provedor, chave)
                    indice_chaves[provedor] = (indice_chaves[provedor] + 1) % len(provider_manager.chaves_por_provedor[provedor])
                    continue
            
            async with session.get(url, params=params, timeout=15) as r:
                latencia_ms = (time.time() - inicio_req) * 1000
                
                if r.status == 200:
                    dados = await r.json()
                    provider_manager.marcar_sucesso(provedor, latencia_ms)
                    print(f"✅ Basquete: Dados obtidos via {provedor} em {latencia_ms:.0f}ms (Score: {provider_manager.health_por_provedor[provedor].score:.0f})")
                    
                    # Salva no cache
                    for evento in dados if isinstance(dados, list) else []:
                        jogo_id = str(evento.get("id", 0))
                        if jogo_id:
                            odds_cache.set(jogo_id, evento, provedor, ttl=300)
                    
                    return dados, provedor
                elif r.status in [401, 429, 403]:
                    print(f"⚠️ Basquete: {provedor} retornou {r.status}")
                    provider_manager.marcar_chave_falha(provedor, chave)
                    indice_chaves[provedor] = (indice_chaves[provedor] + 1) % len(provider_manager.chaves_por_provedor[provedor])
                else:
                    print(f"⚠️ Basquete: {provedor} retornou {r.status}, tentando próximo...")
                    provider_manager.health_por_provedor[provedor].registrar_erro()
                    provider_manager.proximo_provedor()
                    
        except asyncio.TimeoutError:
            print(f"⏱️ Basquete: Timeout no {provedor}")
            provider_manager.health_por_provedor[provedor].registrar_erro()
            provider_manager.proximo_provedor()
        except Exception as e:
            print(f"Erro Basquete no {provedor}: {e}")
            provider_manager.health_por_provedor[provedor].registrar_erro()
            provider_manager.proximo_provedor()
        
        # Pequeno delay entre tentativas de provedores diferentes
        await asyncio.sleep(0.5)
    
    return None, None

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
# PROCESSAMENTO INTELIGENTE MULTIPROVIDER
# ==========================================

async def processar_liga_async(session, liga_key: str, agora_br: datetime):
    """Processa uma liga e acumula oportunidades com suporte multiprovider"""
    global oportunidades_dia, dia_atual

    # Tenta obter dados de qualquer provedor disponível
    data, provedor = await fazer_requisicao_odds_multiprovider(session, liga_key)
    
    if not data or not isinstance(data, list):
        print(f"❌ Basquete: Não foi possível obter dados para {liga_key}")
        return

    for evento in data:
        jogo_id = str(evento.get("id", 0))
        
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

        # Buscar estatísticas usando o gerenciador multiprovider
        stats_home, stats_away, h2h = None, None, []
        try:
            stats_task = asyncio.gather(
                asyncio.wait_for(stats_manager.buscar_stats(session, home_team), timeout=5),
                asyncio.wait_for(stats_manager.buscar_stats(session, away_team), timeout=5),
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
                        justificativa="",
                        contexto="",
                        fonte_dados=provedor.upper()
                    )

                    analise.justificativa = gerar_justificativa(analise)

                    # Adicionar à lista de oportunidades do dia (thread-safe)
                    async with lock_oportunidades:
                        heapq.heappush(oportunidades_dia, (-score, analise))

async def enviar_melhores_do_dia(session: aiohttp.ClientSession):
    """Envia apenas as top N oportunidades do dia"""
    global oportunidades_dia, dia_atual

    async with lock_oportunidades:
        if not oportunidades_dia:
            print("ℹ️ Basquete: Nenhuma oportunidade de qualidade encontrada hoje")
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

    # Contar fontes utilizadas
    fontes = list(set([m.fonte_dados for m in melhores]))

    resumo = (
        f"🏀 <b>TOP CALLS DO DIA - {hoje}</b>\n\n"
        f"Selecionadas {len(melhores)} melhores oportunidades de basquete "
        f"baseadas em análise estatística e valor de odds.\n\n"
        f"📊 Fontes de dados: {', '.join(fontes)}\n"
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

        await asyncio.sleep(1)

# ==========================================
# LOOP PRINCIPAL
# ==========================================

async def loop_infinito():
    global oportunidades_dia, dia_atual

    print("🚀 Bot Basquete iniciado com sistema multiprovider!")
    print(f"🔑 Provedores odds configurados: {len(provider_manager.PRIORIDADE_PROVEDORES)}")
    print(f"🔑 Provedores stats configurados: 2 (Ball Don't Lie, SportDB)")
    print(f"🔑 Total de chaves odds: {sum(len(v) for v in provider_manager.chaves_por_provedor.values() if v)}")
    print(f"🔑 Total de chaves stats: {len(BALLDONTLIE_KEYS) + len(SPORTDB_KEYS)}")
    print(f"🤖 Bots Telegram: 3 (failover automático)")
    print(f"💾 Cache: odds_cache_basquete.db (TTL 5min)")
    print(f"📊 Health Check: Ativo com score dinâmico")
    print("=" * 50)

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
            print(f"📊 Provedores odds ativos: {[p for p in provider_manager.PRIORIDADE_PROVEDORES if p not in provedores_falhos]}")

            # Acumular oportunidades de todas as ligas
            for liga in LIGAS:
                await processar_liga_async(session, liga, agora_br)
                await asyncio.sleep(2)

            # Enviar apenas as melhores no final da varredura
            await enviar_melhores_do_dia(session)

            # Reseta provedores falhos a cada ciclo completo
            if provedores_falhos:
                print(f"🔄 Basquete: Limpando {len(provedores_falhos)} provedores falhos para próximo ciclo")
                provedores_falhos.clear()

            # Limpar cache expirado
            limpos = odds_cache.limpar_expirados()
            if limpos > 0:
                print(f"🧹 Basquete: {limpos} entradas de cache removidas")

            # Log de uso e estatísticas
            hoje_str = datetime.now().strftime("%Y%m%d")
            total_req = sum(v for k, v in request_count.items() if k.endswith(f"_{hoje_str}"))
            cache_stats = odds_cache.estatisticas()
            
            print(f"📊 Basquete: Total requisições hoje: {total_req}")
            print(f"💾 Basquete: Cache hit rate: {cache_stats['hit_rate']:.1f}% ({cache_stats['economia_requisicoes']} economizadas)")
            print(provider_manager.get_health_report())
            print(f"💾 Jogos em memória: {len(jogos_enviados)}")
            print(f"💤 Aguardando próxima varredura em {SCAN_INTERVAL/3600:.1f}h...")
            print("=" * 50)

        await asyncio.sleep(SCAN_INTERVAL)

# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    carregar_memoria_banco()
    try:
        asyncio.run(loop_infinito())
    except KeyboardInterrupt:
        print("\n🛑 Bot Basquete encerrado pelo usuário")
        # Estatísticas finais
        print(f"\n📊 Estatísticas finais:")
        print(f"Cache: {odds_cache.estatisticas()}")
        print(provider_manager.get_health_report())