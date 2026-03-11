import sqlite3
import aiohttp
import asyncio
import json
import statistics
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
from collections import defaultdict
import heapq

# ==========================================
# CONFIGURAÇÕES BOT 2 - AUDITOR PRO MULTIPROVIDER
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

# Configurações de Tokens do Telegram
TELEGRAM_TOKENS = {
    "bot1": "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A",
    "bot2": "8185027087:AAH1JQJKtlWy_oUQpAvqvHEsFIVOK3ScYBc",
    "bot3": "8413563055:AAGyovCDMJOxiAukTbXwaJPm3ZDckIf7qJU"
}

# Usando Bot2 como principal (específico do auditor)
TELEGRAM_TOKEN = TELEGRAM_TOKENS["bot2"]
CHAT_ID_ADMIN = "-1003814625223"
DB_FILE = "probum.db"

MIN_AMOSTRAS_PADRAO = 10
LIMITE_WINRATE_ALERTA = 35.0
LIMITE_ROI_ALERTA = -10.0

# Rate limiting
REQUEST_DELAY = 1.0

# Limites por provedor
MAX_REQ_POR_CHAVE_DIA = {
    "odds_api": 2400,        # 100/hora * 24 = 2400/dia
    "sgo": 1000,             # 1.000 objetos/mês
    "the_odds_token": 500,   # Estimado conservador
    "the_odds_api_legacy": 80
}

# Controle global
api_lock = asyncio.Lock()
request_count = {}
last_request_time = 0
chaves_falhas = {}  # {provider: {chave: timestamp_falha}}
provedores_falhos = set()

# Índices de rotação para cada provedor
indice_chaves = {
    "odds_api": 0,
    "sgo": 0,
    "the_odds_token": 0,
    "the_odds_api_legacy": 0
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
    
    def __init__(self, db_file="odds_cache.db"):
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
# ESTRUTURAS DE DADOS
# ==========================================

@dataclass
class MetricasPeriodo:
    total_apostas: int
    greens: int
    reds: int
    voids: int
    lucro_total: float
    investimento: float
    winrate: float
    roi: float
    media_odd: float
    media_ev: float

@dataclass
class AnalisePadrao:
    categoria: str
    item: str
    amostras: int
    winrate: float
    roi: float
    lucro_total: float
    tendencia: str
    sugestao: str

# ==========================================
# SISTEMA DE FAILOVER MULTIPROVIDER
# ==========================================

class APIProviderManager:
    """Gerencia múltiplos provedores de API com failover automático e health check"""
    
    PRIORIDADE_PROVEDORES = [
        "odds_api",           # 1º: Odds-API.io (melhor custo-benefício)
        "sgo",                # 2º: Sports Game Odds
        "the_odds_token",     # 3º: The Odds Token
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
        print(f"⚠️ Auditor: Chave {chave[:8]}... do {provedor} marcada como falha (Score: {self.health_por_provedor[provedor].score:.0f})")
    
    def marcar_sucesso(self, provedor: str, latencia_ms: float):
        """Registra sucesso no health check"""
        self.health_por_provedor[provedor].registrar_sucesso(latencia_ms)
    
    def marcar_provedor_offline(self, provedor: str):
        """Marca todo o provedor como offline"""
        provedores_falhos.add(provedor)
        print(f"🚫 Auditor: Provedor {provedor} marcado como offline temporariamente")
        
        # Agenda reativação em 30 minutos
        asyncio.create_task(self.reativar_provedor(provedor, 1800))
    
    async def reativar_provedor(self, provedor: str, delay: int):
        """Reativa um provedor após delay"""
        await asyncio.sleep(delay)
        if provedor in provedores_falhos:
            provedores_falhos.remove(provedor)
            self.health_por_provedor[provedor].score = 50  # Reset para valor médio
            print(f"✅ Auditor: Provedor {provedor} reativado")
    
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
# BANCO DE DADOS
# ==========================================

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
            stake REAL DEFAULT 1.5,
            status TEXT DEFAULT 'PENDENTE',
            lucro REAL DEFAULT 0,
            data_hora TEXT,
            pinnacle_odd REAL,
            ranking_score REAL,
            nivel_confianca TEXT,
            justificativa TEXT,
            stats_home TEXT,
            stats_away TEXT,
            horario_envio TEXT,
            tier_liga REAL,
            linha REAL,
            processado_em TEXT,
            fonte_dados TEXT
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analises_historicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_analise TEXT,
            categoria TEXT,
            item TEXT,
            amostras INTEGER,
            winrate REAL,
            roi REAL,
            sugestao_gerada TEXT,
            aplicada BOOLEAN DEFAULT 0
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alertas_sistema (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data_alerta TEXT,
            tipo TEXT,
            mensagem TEXT,
            categoria_afetada TEXT,
            gravidade TEXT,
            resolvido BOOLEAN DEFAULT 0
        )
    """)
    
    conn.commit()
    conn.close()

# ==========================================
# TELEGRAM - MULTIBOT FAILOVER
# ==========================================

async def enviar_telegram_async(session: aiohttp.ClientSession, texto: str):
    """Envia mensagem com failover entre 3 bots"""
    
    # Ordem: Bot2 (principal) → Bot1 → Bot3
    bots = [TELEGRAM_TOKENS["bot2"], TELEGRAM_TOKENS["bot1"], TELEGRAM_TOKENS["bot3"]]
    
    for token in bots:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": CHAT_ID_ADMIN,
            "text": texto,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        try:
            async with session.post(url, json=payload, timeout=10) as r:
                if r.status == 200:
                    return True
                else:
                    print(f"⚠️ Auditor: Bot falhou com status {r.status}, tentando próximo...")
        except Exception as e:
            print(f"Erro Telegram Auditor: {e}")
            continue
    
    print("❌ Auditor: Todos os bots falharam!")
    return False

# ==========================================
# API COM FAILOVER MULTIPROVIDER E CACHE
# ==========================================

async def rate_limit():
    global last_request_time
    agora = datetime.now().timestamp()
    tempo_passado = agora - last_request_time
    if tempo_passado < REQUEST_DELAY:
        await asyncio.sleep(REQUEST_DELAY - tempo_passado)
    last_request_time = datetime.now().timestamp()

async def obter_resultados_api_multiprovider(session: aiohttp.ClientSession, esporte: str, tentativas_max: int = 10):
    """
    Obtém resultados de múltiplos provedores com failover automático, health check e cache
    """
    
    # Primeiro, verifica cache
    # Nota: Para resultados/scores, usamos TTL menor (60s) pois mudam frequentemente
    cache_key = f"resultados_{esporte}"
    cached = odds_cache.get(cache_key)
    if cached:
        print(f"✅ Auditor: Dados obtidos do CACHE para {esporte}")
        return cached
    
    for tentativa in range(tentativas_max):
        provedor = provider_manager.get_provedor_atual()
        
        if not provedor:
            print("❌ Auditor: Nenhum provedor disponível! Aguardando...")
            await asyncio.sleep(300)
            provedores_falhos.clear()
            continue
        
        chave, idx = provider_manager.get_chave_valida(provedor)
        
        if not chave:
            print(f"⚠️ Auditor: Todas as chaves do {provedor} esgotadas")
            provider_manager.marcar_provedor_offline(provedor)
            provider_manager.proximo_provedor()
            continue
        
        await rate_limit()
        
        inicio_req = time.time()
        
        # Constrói URL conforme o provedor
        if provedor in ["odds_api", "the_odds_token", "the_odds_api_legacy"]:
            url = f"https://api.the-odds-api.com/v4/sports/{esporte}/scores/"
            params = {
                "apiKey": chave,
                "daysFrom": 3,
                "dateFormat": "iso"
            }
        elif provedor == "sgo":
            url = "https://api.sportsgameodds.com/v1/results"
            params = {
                "apiKey": chave,
                "sport": esporte.replace("basketball_", "").replace("soccer_", ""),
                "days": 3
            }
        else:
            url = f"https://api.the-odds-api.com/v4/sports/{esporte}/scores/"
            params = {"apiKey": chave, "daysFrom": 3, "dateFormat": "iso"}
        
        try:
            hoje = datetime.now().strftime("%Y%m%d")
            chave_hoje = f"{provedor}_{chave}_{hoje}"
            
            async with api_lock:
                request_count[chave_hoje] = request_count.get(chave_hoje, 0) + 1
                
                if request_count[chave_hoje] >= MAX_REQ_POR_CHAVE_DIA.get(provedor, 80):
                    print(f"⚠️ Auditor: Limite diário atingido para {provedor}")
                    provider_manager.marcar_chave_falha(provedor, chave)
                    indice_chaves[provedor] = (indice_chaves[provedor] + 1) % len(provider_manager.chaves_por_provedor[provedor])
                    continue
            
            async with session.get(url, params=params, timeout=15) as r:
                latencia_ms = (time.time() - inicio_req) * 1000
                
                if r.status == 200:
                    dados = await r.json()
                    provider_manager.marcar_sucesso(provedor, latencia_ms)
                    print(f"✅ Auditor: Dados obtidos via {provedor} em {latencia_ms:.0f}ms (Score: {provider_manager.health_por_provedor[provedor].score:.0f})")
                    
                    # Salva no cache (TTL curto para resultados: 60 segundos)
                    odds_cache.set(cache_key, {"data": dados, "timestamp": datetime.now().timestamp()}, provedor, ttl=60)
                    
                    return dados
                elif r.status in [401, 429, 403]:
                    print(f"⚠️ Auditor: {provedor} retornou {r.status}")
                    provider_manager.marcar_chave_falha(provedor, chave)
                    indice_chaves[provedor] = (indice_chaves[provedor] + 1) % len(provider_manager.chaves_por_provedor[provedor])
                else:
                    print(f"⚠️ Auditor: {provedor} retornou {r.status}, tentando próximo...")
                    provider_manager.health_por_provedor[provedor].registrar_erro()
                    provider_manager.proximo_provedor()
                    
        except asyncio.TimeoutError:
            print(f"⏱️ Auditor: Timeout no {provedor}")
            provider_manager.health_por_provedor[provedor].registrar_erro()
            provider_manager.proximo_provedor()
        except Exception as e:
            print(f"Erro Auditor no {provedor}: {e}")
            provider_manager.health_por_provedor[provedor].registrar_erro()
            provider_manager.proximo_provedor()
        
        await asyncio.sleep(0.5)
    
    return []

def resolver_aposta_completa(aposta: sqlite3.Row, placar: Dict) -> Tuple[str, float, str]:
    mercado = aposta['mercado'].upper()
    selecao = aposta['selecao']
    odd = aposta['odd']
    stake = aposta['stake']
    
    scores = placar.get("scores", [])
    if not scores:
        return "PENDENTE", 0, "Sem placar"
    
    h_team = placar["home_team"]
    a_team = placar["away_team"]
    h_score = next((int(s["score"]) for s in scores if s["name"] == h_team), 0)
    a_score = next((int(s["score"]) for s in scores if s["name"] == a_team), 0)
    total = h_score + a_score
    status = "RED"
    detalhes = ""
    
    if aposta['esporte'] == 'soccer':
        if "H2H" in mercado or "VENCEDOR" in mercado:
            if "1" in selecao and h_score > a_score:
                status = "GREEN"
                detalhes = f"{h_team} venceu {h_score}x{a_score}"
            elif "2" in selecao and a_score > h_score:
                status = "GREEN"
                detalhes = f"{a_team} venceu {a_score}x{h_score}"
            elif ("X" in selecao or "EMPATE" in selecao) and h_score == a_score:
                status = "GREEN"
                detalhes = f"Empate {h_score}x{a_score}"
        
        elif "BTTS" in mercado or "AMBAS" in mercado:
            if "SIM" in selecao.upper() and h_score > 0 and a_score > 0:
                status = "GREEN"
                detalhes = "Ambas marcaram"
            elif "NÃO" in selecao.upper() and (h_score == 0 or a_score == 0):
                status = "GREEN"
                detalhes = "Pelo menos um não marcou"
        
        elif "TOTAL" in mercado or "GOLS" in mercado:
            try:
                linha = float(''.join(c for c in selecao if c.isdigit() or c == '.'))
                if "OVER" in selecao.upper() and total > linha:
                    status = "GREEN"
                    detalhes = f"Over {total} > {linha}"
                elif "UNDER" in selecao.upper() and total < linha:
                    status = "GREEN"
                    detalhes = f"Under {total} < {linha}"
                elif total == linha:
                    status = "REEMBOLSO"
                    detalhes = f"Push {total}"
            except:
                pass
    
    elif aposta['esporte'] == 'basketball':
        if "H2H" in mercado or "VENCEDOR" in mercado:
            if h_team in selecao and h_score > a_score:
                status = "GREEN"
                detalhes = f"{h_team} venceu {h_score}x{a_score}"
            elif a_team in selecao and a_score > h_score:
                status = "GREEN"
                detalhes = f"{a_team} venceu {a_score}x{h_score}"
        
        elif "SPREAD" in mercado or "HANDICAP" in mercado:
            try:
                linha = float(''.join(c for c in selecao if c.isdigit() or c in '.-'))
                if h_team in selecao:
                    resultado = h_score + linha - a_score
                    time_apostado = h_team
                else:
                    resultado = a_score + linha - h_score
                    time_apostado = a_team
                
                if resultado > 0:
                    status = "GREEN"
                    detalhes = f"{time_apostado} cobriu {linha}"
                elif resultado == 0:
                    status = "REEMBOLSO"
                    detalhes = "Push spread"
                else:
                    detalhes = f"{time_apostado} não cobriu"
            except:
                pass
        
        elif "TOTAL" in mercado or "PONTOS" in mercado:
            try:
                linha = float(''.join(c for c in selecao if c.isdigit() or c == '.'))
                if "OVER" in selecao.upper() and total > linha:
                    status = "GREEN"
                    detalhes = f"Over {total} > {linha}"
                elif "UNDER" in selecao.upper() and total < linha:
                    status = "GREEN"
                    detalhes = f"Under {total} < {linha}"
                elif total == linha:
                    status = "REEMBOLSO"
                    detalhes = f"Push {total}"
            except:
                pass
    
    if status == "GREEN":
        lucro = (stake * odd) - stake
    elif status == "REEMBOLSO":
        lucro = 0
    else:
        lucro = -stake
    
    return status, lucro, detalhes

# ==========================================
# ANÁLISE ESTATÍSTICA AVANÇADA
# ==========================================

def calcular_metricas(apostas: List[sqlite3.Row]) -> MetricasPeriodo:
    if not apostas:
        return MetricasPeriodo(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    
    total = len(apostas)
    greens = sum(1 for a in apostas if a['status'] == 'GREEN')
    reds = sum(1 for a in apostas if a['status'] == 'RED')
    voids = sum(1 for a in apostas if a['status'] == 'REEMBOLSO')
    lucro_total = sum(a['lucro'] for a in apostas)
    investimento = sum(a['stake'] for a in apostas)
    winrate = (greens / (greens + reds) * 100) if (greens + reds) > 0 else 0
    roi = (lucro_total / investimento * 100) if investimento > 0 else 0
    odds = [a['odd'] for a in apostas if a['odd']]
    media_odd = statistics.mean(odds) if odds else 0
    evs = [a['ev'] for a in apostas if a['ev']]
    media_ev = statistics.mean(evs) if evs else 0
    
    return MetricasPeriodo(total, greens, reds, voids, lucro_total, investimento, winrate, roi, media_odd, media_ev)

def analisar_padroes(conn: sqlite3.Connection, dias_historico: int = 14) -> List[AnalisePadrao]:
    data_corte = (datetime.now(ZoneInfo("America/Sao_Paulo")) - timedelta(days=dias_historico)).strftime('%d/%m/%Y')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM operacoes_tipster WHERE data_hora >= ? AND status != 'PENDENTE'", (data_corte,))
    apostas = cursor.fetchall()
    
    if len(apostas) < MIN_AMOSTRAS_PADRAO:
        return []
    
    analises = []
    
    # Por mercado
    mercados = defaultdict(list)
    for a in apostas:
        mercados[a['mercado']].append(a)
    for mercado, lista in mercados.items():
        if len(lista) >= MIN_AMOSTRAS_PADRAO:
            m = calcular_metricas(lista)
            if m.roi < LIMITE_ROI_ALERTA:
                analises.append(AnalisePadrao('mercado', mercado, len(lista), m.winrate, m.roi, m.lucro_total, 'negativa', f"Revisar {mercado} (ROI: {m.roi:.1f}%)"))
            elif m.roi > 15:
                analises.append(AnalisePadrao('mercado', mercado, len(lista), m.winrate, m.roi, m.lucro_total, 'positiva', f"Priorizar {mercado} (ROI: {m.roi:.1f}%)"))
    
    # Por liga
    ligas = defaultdict(list)
    for a in apostas:
        ligas[a['liga']].append(a)
    for liga, lista in ligas.items():
        if len(lista) >= MIN_AMOSTRAS_PADRAO:
            m = calcular_metricas(lista)
            if m.winrate < LIMITE_WINRATE_ALERTA:
                analises.append(AnalisePadrao('liga', liga, len(lista), m.winrate, m.roi, m.lucro_total, 'negativa', f"Pausar {liga} (Winrate: {m.winrate:.1f}%)"))
            elif m.winrate > 60 and m.roi > 10:
                analises.append(AnalisePadrao('liga', liga, len(lista), m.winrate, m.roi, m.lucro_total, 'positiva', f"Focar em {liga} (Winrate: {m.winrate:.1f}%)"))
    
    # Por fonte de dados (provedor de odds)
    fontes = defaultdict(list)
    for a in apostas:
        fonte = a['fonte_dados'] or 'desconhecida'
        fontes[fonte].append(a)
    for fonte, lista in fontes.items():
        if len(lista) >= MIN_AMOSTRAS_PADRAO:
            m = calcular_metricas(lista)
            if m.roi < LIMITE_ROI_ALERTA:
                analises.append(AnalisePadrao('fonte', fonte, len(lista), m.winrate, m.roi, m.lucro_total, 'negativa', f"Revisar provedor {fonte} (ROI: {m.roi:.1f}%)"))
            elif m.roi > 15:
                analises.append(AnalisePadrao('fonte', fonte, len(lista), m.winrate, m.roi, m.lucro_total, 'positiva', f"Priorizar provedor {fonte} (ROI: {m.roi:.1f}%)"))
    
    # Por horário do dia (identificar melhores horários)
    horarios = defaultdict(list)
    for a in apostas:
        try:
            hora = datetime.strptime(a['data_hora'], '%d/%m/%Y').hour if ':' not in a['data_hora'] else datetime.strptime(a['data_hora'], '%d/%m/%Y %H:%M').hour
            faixa = f"{hora:02d}h-{(hora+2):02d}h"
            horarios[faixa].append(a)
        except:
            pass
    
    for faixa, lista in horarios.items():
        if len(lista) >= MIN_AMOSTRAS_PADRAO:
            m = calcular_metricas(lista)
            if m.roi < LIMITE_ROI_ALERTA:
                analises.append(AnalisePadrao('horario', faixa, len(lista), m.winrate, m.roi, m.lucro_total, 'negativa', f"Evitar apostas {faixa} (ROI: {m.roi:.1f}%)"))
            elif m.roi > 15:
                analises.append(AnalisePadrao('horario', faixa, len(lista), m.winrate, m.roi, m.lucro_total, 'positiva', f"Focar em apostas {faixa} (ROI: {m.roi:.1f}%)"))
    
    return analises

# ==========================================
# AUDITORIA COMPLETA
# ==========================================

async def rotina_auditoria_completa(session: aiohttp.ClientSession):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM operacoes_tipster WHERE status='PENDENTE'")
    pendentes = cursor.fetchall()
    
    if not pendentes:
        print("☕ Auditor: Nenhuma aposta pendente.")
        conn.close()
        return
    
    print(f"🔍 Auditando {len(pendentes)} apostas...")
    
    esportes = set(p['esporte'] for p in pendentes)
    resultados_por_esporte = {}
    
    for esporte in esportes:
        resultados = await obter_resultados_api_multiprovider(session, esporte)
        if resultados:
            resultados_por_esporte[esporte] = resultados
    
    atualizadas = []
    for aposta in pendentes:
        esporte = aposta['esporte']
        if esporte not in resultados_por_esporte:
            continue
        
        for placar in resultados_por_esporte[esporte]:
            if not placar.get("completed"):
                continue
            
            if aposta['id_aposta'].startswith(placar['id']):
                status, lucro, detalhes = resolver_aposta_completa(aposta, placar)
                if status != "PENDENTE":
                    agora = datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat()
                    cursor.execute(
                        "UPDATE operacoes_tipster SET status=?, lucro=?, processado_em=?, justificativa=COALESCE(justificativa,'') || ' | ' || ? WHERE id_aposta=?",
                        (status, lucro, agora, detalhes, aposta['id_aposta'])
                    )
                    atualizadas.append((aposta, status, lucro))
                    print(f"  ✅ {aposta['jogo']}: {status}")
                break
    
    conn.commit()
    
    if atualizadas:
        padroes = analisar_padroes(conn)
        for padrao in padroes:
            if padrao.tendencia == 'negativa':
                cursor.execute(
                    "SELECT id FROM alertas_sistema WHERE categoria_afetada=? AND tipo=? AND resolvido=0",
                    (padrao.categoria, padrao.item)
                )
                if not cursor.fetchone():
                    cursor.execute(
                        "INSERT INTO alertas_sistema (data_alerta, tipo, mensagem, categoria_afetada, gravidade) VALUES (?, ?, ?, ?, ?)",
                        (datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(), padrao.item, padrao.sugestao, padrao.categoria, 'ALTA' if padrao.roi < -20 else 'MÉDIA')
                    )
        conn.commit()
        
        alertas_novos = [p for p in padroes if p.tendencia == 'negativa']
        if alertas_novos:
            await enviar_alertas(session, alertas_novos)
    
    conn.close()
    print(f"✅ Auditor: {len(atualizadas)} apostas atualizadas.")
    
    # Limpar cache expirado a cada execução
    limpos = odds_cache.limpar_expirados()
    if limpos > 0:
        print(f"🧹 Auditor: {limpos} entradas de cache removidas")

async def enviar_alertas(session: aiohttp.ClientSession, alertas: List[AnalisePadrao]):
    texto = "🚨 <b>ALERTAS DO SISTEMA</b>\n\nPadrões detectados:\n\n"
    for alerta in alertas[:5]:
        emoji = "🔴" if alerta.roi < -20 else "🟡"
        texto += f"{emoji} <b>{alerta.categoria.upper()}:</b> {alerta.item}\nAmostras: {alerta.amostras} | Winrate: {alerta.winrate:.1f}% | ROI: {alerta.roi:.1f}%\n💡 {alerta.sugestao}\n\n"
    texto += "⚠️ <i>Ajustar filtros dos bots conforme sugestões.</i>"
    await enviar_telegram_async(session, texto)

# ==========================================
# RELATÓRIOS AVANÇADOS
# ==========================================

async def gerar_relatorio_diario(session: aiohttp.ClientSession):
    data_alvo = (datetime.now(ZoneInfo("America/Sao_Paulo")) - timedelta(days=1)).strftime('%d/%m/%Y')
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM operacoes_tipster WHERE data_hora=? AND status!='PENDENTE'", (data_alvo,))
    apostas_dia = cursor.fetchall()
    
    if not apostas_dia:
        await enviar_telegram_async(session, f"📊 <b>RELATÓRIO DIÁRIO ({data_alvo})</b>\n\nNenhuma aposta finalizada.")
        conn.close()
        return
    
    metricas = calcular_metricas(apostas_dia)
    futebol = [a for a in apostas_dia if a['esporte'] == 'soccer']
    basquete = [a for a in apostas_dia if a['esporte'] == 'basketball']
    m_fut = calcular_metricas(futebol)
    m_bas = calcular_metricas(basquete)
    
    padroes = analisar_padroes(conn, dias_historico=7)
    oportunidades = [p for p in padroes if p.tendencia == 'positiva']
    problemas = [p for p in padroes if p.tendencia == 'negativa']
    
    # Estatísticas de cache
    cache_stats = odds_cache.estatisticas()
    
    emoji = "💰" if metricas.lucro_total >= 0 else "🩸"
    
    texto = (
        f"📊 <b>RELATÓRIO DIÁRIO SINDICATO ({data_alvo})</b>\n\n"
        f"<b>📈 RESUMO GERAL</b>\n"
        f"Total: {metricas.total_apostas} | ✅ Greens: {metricas.greens} | ❌ Reds: {metricas.reds} | 🔄 Void: {metricas.voids}\n"
        f"🎯 Winrate: {metricas.winrate:.1f}% | 💵 Investido: {metricas.investimento:.2f}u\n"
        f"{emoji} Resultado: {metricas.lucro_total:+.2f}u | 📊 ROI: {metricas.roi:.2f}%\n"
        f"📉 Odd média: {metricas.media_odd:.2f} | EV médio: {metricas.media_ev*100:.2f}%\n\n"
    )
    
    if futebol:
        emoji_fut = "🟢" if m_fut.lucro_total >= 0 else "🔴"
        texto += f"<b>⚽ FUTEBOL (Bot 1)</b>\nApostas: {m_fut.total_apostas} | Winrate: {m_fut.winrate:.1f}%\nResultado: {emoji_fut} {m_fut.lucro_total:+.2f}u (ROI: {m_fut.roi:.1f}%)\n\n"
    
    if basquete:
        emoji_bas = "🟢" if m_bas.lucro_total >= 0 else "🔴"
        texto += f"<b>🏀 BASQUETE (Bot 3)</b>\nApostas: {m_bas.total_apostas} | Winrate: {m_bas.winrate:.1f}%\nResultado: {emoji_bas} {m_bas.lucro_total:+.2f}u (ROI: {m_bas.roi:.1f}%)\n\n"
    
    if oportunidades:
        texto += f"<b>💎 OPORTUNIDADES (7 dias)</b>\n"
        for opp in oportunidades[:3]:
            texto += f"✨ {opp.categoria}: {opp.item} (Winrate: {opp.winrate:.1f}%, ROI: {opp.roi:.1f}%)\n"
        texto += "\n"
    
    if problemas:
        texto += f"<b>⚠️ ATENÇÃO</b>\n"
        for prob in problemas[:2]:
            texto += f"🔍 {prob.sugestao}\n"
        texto += "\n"
    
    # Health check dos provedores
    texto += f"<b>🔧 INFRAESTRUTURA</b>\n"
    texto += f"💾 Cache: {cache_stats['hit_rate']:.1f}% hit rate ({cache_stats['economia_requisicoes']} reqs economizadas)\n"
    health_report = provider_manager.get_health_report().replace("\n", "\n")
    texto += f"{health_report}\n\n"
    
    inicio_mes = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(day=1).strftime('%d/%m/%Y')
    cursor.execute("SELECT * FROM operacoes_tipster WHERE data_hora >= ? AND status!='PENDENTE'", (inicio_mes,))
    apostas_mes = cursor.fetchall()
    m_mes = calcular_metricas(apostas_mes)
    
    texto += (
        f"<b>📅 ACUMULADO DO MÊS</b>\n"
        f"Apostas: {m_mes.total_apostas} | Winrate: {m_mes.winrate:.1f}%\n"
        f"Resultado: {'💰' if m_mes.lucro_total >= 0 else '🩸'} {m_mes.lucro_total:+.2f}u | ROI: {m_mes.roi:.2f}%"
    )
    
    conn.close()
    await enviar_telegram_async(session, texto)

async def gerar_relatorio_semanal(session: aiohttp.ClientSession):
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo"))
    inicio_semana = (hoje - timedelta(days=7)).strftime('%d/%m/%Y')
    
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM operacoes_tipster WHERE data_hora >= ? AND status!='PENDENTE'", (inicio_semana,))
    apostas = cursor.fetchall()
    
    if len(apostas) < 5:
        conn.close()
        return
    
    metricas = calcular_metricas(apostas)
    resultados = [a['status'] for a in apostas]
    sequencia_atual = 0
    for r in reversed(resultados):
        if r == 'GREEN':
            sequencia_atual += 1
        else:
            break
    
    dias = defaultdict(list)
    for a in apostas:
        dias[a['data_hora']].append(a)
    lucro_por_dia = {d: sum(a['lucro'] for a in lista) for d, lista in dias.items()}
    melhor_dia = max(lucro_por_dia.items(), key=lambda x: x[1])
    pior_dia = min(lucro_por_dia.items(), key=lambda x: x[1])
    
    # Análise por provedor na semana
    cursor.execute("""
        SELECT fonte_dados, COUNT(*) as total, 
               SUM(CASE WHEN status='GREEN' THEN 1 ELSE 0 END) as greens,
               SUM(lucro) as lucro_total
        FROM operacoes_tipster 
        WHERE data_hora >= ? AND status != 'PENDENTE' AND fonte_dados IS NOT NULL
        GROUP BY fonte_dados
    """, (inicio_semana,))
    por_provedor = cursor.fetchall()
    
    texto = (
        f"📈 <b>RELATÓRIO SEMANAL</b>\n\n"
        f"<b>Período:</b> {inicio_semana} a {hoje.strftime('%d/%m/%Y')}\n\n"
        f"<b>📊 Métricas</b>\n"
        f"Total: {metricas.total_apostas} | Winrate: {metricas.winrate:.1f}% | ROI: {metricas.roi:.2f}%\n"
        f"Lucro: {'💰' if metricas.lucro_total >= 0 else '🩸'} {metricas.lucro_total:+.2f}u\n"
        f"Sequência atual: {sequencia_atual} greens\n\n"
        f"<b>📅 Por Dia</b>\n"
        f"🟢 Melhor: {melhor_dia[0]} ({melhor_dia[1]:+.2f}u)\n"
        f"🔴 Pior: {pior_dia[0]} ({pior_dia[1]:+.2f}u)\n\n"
    )
    
    if por_provedor:
        texto += f"<b>🔌 Performance por Provedor</b>\n"
        for row in por_provedor:
            nome, total, greens, lucro = row
            wr = (greens / total * 100) if total > 0 else 0
            emoji = "🟢" if lucro > 0 else "🔴"
            texto += f"{emoji} {nome}: {total} bets | WR: {wr:.1f}% | Lucro: {lucro:+.2f}u\n"
        texto += "\n"
    
    texto += f"<b>💡 Recomendações</b>\n"
    
    padroes = analisar_padroes(conn, dias_historico=7)
    positivos = [p for p in padroes if p.tendencia == 'positiva']
    negativos = [p for p in padroes if p.tendencia == 'negativa']
    
    if positivos:
        texto += "✅ <b>Continuar:</b>\n"
        for p in positivos[:2]:
            texto += f"   • {p.categoria}: {p.item}\n"
    
    if negativos:
        texto += "\n⚠️ <b>Revisar:</b>\n"
        for p in negativos[:2]:
            texto += f"   • {p.categoria}: {p.item}\n"
    
    conn.close()
    await enviar_telegram_async(session, texto)

# ==========================================
# LOOP PRINCIPAL
# ==========================================

async def loop_principal():
    inicializar_banco()
    
    print("🚀 Bot Auditor iniciado com sistema multiprovider!")
    print(f"🔑 Provedores configurados: {len(provider_manager.PRIORIDADE_PROVEDORES)}")
    print(f"🔑 Total de chaves: {sum(len(v) for v in provider_manager.chaves_por_provedor.values())}")
    print(f"💾 Cache: odds_cache.db (TTL 60s para resultados)")
    print(f"🤖 Bots Telegram: 3 (failover automático)")
    print(f"📊 Health Check: Ativo com score dinâmico")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        while True:
            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
            
            # Executa auditoria a cada hora
            await rotina_auditoria_completa(session)
            
            # Relatório diário às 9h
            if agora.hour == 9 and agora.minute < 5:
                await gerar_relatorio_diario(session)
                await asyncio.sleep(300)  # Evita múltiplos envios
            
            # Relatório semanal às 10h de segunda
            if agora.weekday() == 0 and agora.hour == 10 and agora.minute < 5:
                await gerar_relatorio_semanal(session)
                await asyncio.sleep(300)
            
            # Limpa provedores falhos a cada ciclo
            if provedores_falhos:
                print(f"🔄 Auditor: Limpando {len(provedores_falhos)} provedores falhos")
                provedores_falhos.clear()
            
            # Log de uso e health check
            hoje = datetime.now().strftime("%Y%m%d")
            total_req = sum(v for k, v in request_count.items() if k.endswith(f"_{hoje}"))
            cache_stats = odds_cache.estatisticas()
            
            print(f"📊 Auditor: Total requisições hoje: {total_req}")
            print(f"💾 Cache: {cache_stats['hit_rate']:.1f}% hit rate, {cache_stats['economia_requisicoes']} economizadas")
            print(provider_manager.get_health_report())
            print(f"💤 Aguardando próxima auditoria em 1h...")
            print("=" * 50)
            
            await asyncio.sleep(3600)  # Aguarda 1 hora

# ==========================================
# START
# ==========================================

if __name__ == "__main__":
    try:
        asyncio.run(loop_principal())
    except KeyboardInterrupt:
        print("\n🛑 Bot Auditor encerrado pelo usuário")
        # Estatísticas finais
        print(f"\n📊 Estatísticas finais:")
        print(f"Cache: {odds_cache.estatisticas()}")
        print(provider_manager.get_health_report())