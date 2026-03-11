"""
Módulo core compartilhado entre todos os bots do ProBum
Contém: Circuit Breaker, Cache Distribuído, e Gerenciamento de Provedores
"""

import asyncio
import aiohttp
import sqlite3
import json
import statistics
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Tuple, Any
from collections import defaultdict
import os

# ==========================================
# CONFIGURAÇÕES GLOBAIS
# ==========================================

DB_CACHE_FILE = "odds_cache.db"
DB_MAIN_FILE = "probum.db"

# ==========================================
# CIRCUIT BREAKER INTELIGENTE
# ==========================================

@dataclass
class ProvedorHealth:
    """Monitora saúde de cada provedor em tempo real"""
    nome: str
    latencias: List[float] = field(default_factory=list)
    erros_consecutivos: int = 0
    sucessos_consecutivos: int = 0
    ultimo_sucesso: Optional[datetime] = None
    ultimo_erro: Optional[datetime] = None
    score: float = 100.0  # 0-100
    total_requisicoes: int = 0
    total_erros: int = 0
    
    def registrar_sucesso(self, latencia_ms: float):
        """Registra requisição bem-sucedida"""
        self.latencias.append(latencia_ms)
        if len(self.latencias) > 10:
            self.latencias.pop(0)
        
        self.erros_consecutivos = 0
        self.sucessos_consecutivos += 1
        self.ultimo_sucesso = datetime.now()
        self.total_requisicoes += 1
        
        # Recuperação gradual do score
        self.score = min(100.0, self.score + 5.0)
    
    def registrar_erro(self, tipo_erro: str = "unknown"):
        """Registra falha"""
        self.erros_consecutivos += 1
        self.sucessos_consecutivos = 0
        self.ultimo_erro = datetime.now()
        self.total_requisicoes += 1
        self.total_erros += 1
        
        # Penalidade exponencial para erros consecutivos
        penalidade = 10.0 * (2 ** self.erros_consecutivos)
        self.score = max(0.0, self.score - penalidade)
    
    def get_latencia_media(self) -> float:
        """Retorna latência média das últimas requisições"""
        if not self.latencias:
            return 9999.0
        return statistics.mean(self.latencias)
    
    def esta_saudavel(self) -> bool:
        """Determina se provedor pode ser usado"""
        # Score mínimo de 30
        # Máximo de 3 erros consecutivos
        # Latência média abaixo de 5 segundos
        return (
            self.score > 30.0 and 
            self.erros_consecutivos < 3 and
            self.get_latencia_media() < 5000.0
        )
    
    def get_status(self) -> str:
        """Retorna status legível"""
        if self.esta_saudavel():
            return f"🟢 SAUDÁVEL (score: {self.score:.0f}, lat: {self.get_latencia_media():.0f}ms)"
        elif self.score > 0:
            return f"🟡 DEGRADADO (score: {self.score:.0f}, erros: {self.erros_consecutivos})"
        else:
            return f"🔴 OFFLINE (score: {self.score:.0f})"


class CircuitBreakerManager:
    """Gerencia health check de todos os provedores"""
    
    def __init__(self):
        self.health_por_provedor: Dict[str, ProvedorHealth] = {}
    
    def get_health(self, provedor: str) -> ProvedorHealth:
        """Obtém ou cria monitor de saúde"""
        if provedor not in self.health_por_provedor:
            self.health_por_provedor[provedor] = ProvedorHealth(nome=provedor)
        return self.health_por_provedor[provedor]
    
    def ordenar_por_saude(self, provedores: List[str]) -> List[str]:
        """Ordena provedores do mais saudável para o menos"""
        scores = []
        for p in provedores:
            health = self.get_health(p)
            # Prioridade: score alto, latência baixa, menos erros
            prioridade = (
                health.score * 10 -
                health.get_latencia_media() / 100 -
                health.erros_consecutivos * 50
            )
            scores.append((prioridade, p))
        
        scores.sort(reverse=True)
        return [p for _, p in scores]
    
    def get_relatorio(self) -> str:
        """Gera relatório de saúde de todos os provedores"""
        linhas = ["📊 SAÚDE DOS PROVEDORES:"]
        for nome, health in sorted(self.health_por_provedor.items()):
            linhas.append(f"  {nome}: {health.get_status()}")
        return "\n".join(linhas)


# Instância global do circuit breaker
circuit_breaker = CircuitBreakerManager()

# ==========================================
# CACHE DISTRIBUÍDO DE ODDS
# ==========================================

class OddsCache:
    """Cache compartilhado entre todos os bots"""
    
    def __init__(self, db_file: str = DB_CACHE_FILE):
        self.db_file = db_file
        self._init_db()
        self._local_cache: Dict[str, Any] = {}  # Cache em memória (mais rápido)
        self._local_ttl: Dict[str, float] = {}
    
    def _init_db(self):
        """Inicializa banco de cache"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS odds_cache (
                jogo_id TEXT PRIMARY KEY,
                liga TEXT,
                esporte TEXT,
                dados_json TEXT,
                provedor TEXT,
                timestamp REAL,
                ttl INTEGER DEFAULT 300,
                acessos INTEGER DEFAULT 1
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_stats (
                data TEXT PRIMARY KEY,
                hits INTEGER DEFAULT 0,
                misses INTEGER DEFAULT 0,
                economia_requisicoes INTEGER DEFAULT 0
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _get_hoje(self) -> str:
        return datetime.now().strftime("%Y-%m-%d")
    
    def _update_stats(self, hit: bool):
        """Atualiza estatísticas de uso"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            hoje = self._get_hoje()
            
            cursor.execute("INSERT OR IGNORE INTO cache_stats (data) VALUES (?)", (hoje,))
            
            if hit:
                cursor.execute("UPDATE cache_stats SET hits = hits + 1 WHERE data = ?", (hoje,))
            else:
                cursor.execute("UPDATE cache_stats SET misses = misses + 1 WHERE data = ?", (hoje,))
            
            conn.commit()
            conn.close()
        except:
            pass
    
    def get(self, jogo_id: str, max_age: int = 300) -> Optional[Dict]:
        """
        Busca no cache (memória -> disco)
        max_age: idade máxima em segundos (padrão 5 min)
        """
        agora = datetime.now().timestamp()
        
        # 1. Tentar cache local (memória) - mais rápido
        if jogo_id in self._local_cache:
            if agora - self._local_ttl.get(jogo_id, 0) < max_age:
                self._update_stats(True)
                return self._local_cache[jogo_id]
            else:
                # Expirou, remover
                del self._local_cache[jogo_id]
                del self._local_ttl[jogo_id]
        
        # 2. Tentar cache em disco
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dados_json, timestamp, ttl, provedor 
                FROM odds_cache 
                WHERE jogo_id = ?
            """, (jogo_id,))
            
            row = cursor.fetchone()
            
            if row:
                dados_json, timestamp, ttl, provedor = row
                if agora - timestamp < min(ttl, max_age):
                    # Cache hit! Atualizar contador de acessos
                    cursor.execute("""
                        UPDATE odds_cache 
                        SET acessos = acessos + 1 
                        WHERE jogo_id = ?
                    """, (jogo_id,))
                    conn.commit()
                    conn.close()
                    
                    # Popular cache local
                    dados = json.loads(dados_json)
                    self._local_cache[jogo_id] = dados
                    self._local_ttl[jogo_id] = agora
                    
                    self._update_stats(True)
                    return dados
            
            conn.close()
        except Exception as e:
            print(f"⚠️ Erro ao ler cache: {e}")
        
        self._update_stats(False)
        return None
    
    def set(self, jogo_id: str, dados: Dict, provedor: str, 
            ttl: int = 300, esporte: str = "unknown", liga: str = "unknown"):
        """Salva no cache (memória e disco)"""
        agora = datetime.now().timestamp()
        
        # Salvar em memória
        self._local_cache[jogo_id] = dados
        self._local_ttl[jogo_id] = agora
        
        # Salvar em disco (async, não bloqueia)
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO odds_cache 
                (jogo_id, liga, esporte, dados_json, provedor, timestamp, ttl, acessos)
                VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT acessos FROM odds_cache WHERE jogo_id = ?), 0))
            """, (
                jogo_id, liga, esporte, json.dumps(dados), provedor, agora, ttl, jogo_id
            ))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"⚠️ Erro ao salvar cache: {e}")
    
    def get_stats(self) -> Dict:
        """Retorna estatísticas de uso do cache"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            hoje = self._get_hoje()
            
            cursor.execute("""
                SELECT hits, misses, economia_requisicoes 
                FROM cache_stats WHERE data = ?
            """, (hoje,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                hits, misses, economia = row
                total = hits + misses
                hit_rate = (hits / total * 100) if total > 0 else 0
                return {
                    "hits": hits,
                    "misses": misses,
                    "hit_rate": hit_rate,
                    "economia_requisicoes": economia,
                    "total_consultas": total
                }
        except:
            pass
        
        return {"hits": 0, "misses": 0, "hit_rate": 0, "economia_requisicoes": 0, "total_consultas": 0}
    
    def limpar_antigos(self, max_age_hours: int = 24):
        """Remove entradas antigas do cache em disco"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            limite = (datetime.now() - timedelta(hours=max_age_hours)).timestamp()
            
            cursor.execute("DELETE FROM odds_cache WHERE timestamp < ?", (limite,))
            deletados = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deletados > 0:
                print(f"🧹 Cache limpo: {deletados} entradas antigas removidas")
        except Exception as e:
            print(f"⚠️ Erro ao limpar cache: {e}")


# Instância global do cache
odds_cache = OddsCache()

# ==========================================
# GERENCIADOR DE PROVEDORES UNIFICADO
# ==========================================

class APIProviderManager:
    """Gerenciador unificado com Circuit Breaker e Cache"""
    
    def __init__(self, provedores_config: Dict[str, List[str]]):
        """
        provedores_config: { "odds_api": ["chave1", "chave2"], ... }
        """
        self.chaves_por_provedor = provedores_config
        self.health_manager = circuit_breaker
        self.cache = odds_cache
        self.indice_chaves = {p: 0 for p in provedores_config.keys()}
        self.chaves_falhas: Dict[str, Dict[str, float]] = {p: {} for p in provedores_config.keys()}
        self.provedores_offline: set = set()
        
        # URLs base por provedor
        self.urls_base = {
            "odds_api": "https://api.the-odds-api.com/v4/sports",
            "sgo": "https://api.sportsgameodds.com/v1",
            "the_odds_token": "https://api.the-odds-api.com/v4/sports",
            "the_odds_api_legacy": "https://api.the-odds-api.com/v4/sports",
            "api_football": "https://v3.football.api-sports.io",
            "sportmonks": "https://api.sportmonks.com/v3/football",
            "balldontlie": "https://api.balldontlie.io/v1",
            "sportsdb": "https://www.thesportsdb.com/api/v1/json"
        }
    
    def get_provedores_ordenados(self) -> List[str]:
        """Retorna provedores ordenados por saúde (mais saudáveis primeiro)"""
        disponiveis = [p for p in self.chaves_por_provedor.keys() 
                      if p not in self.provedores_offline]
        return self.health_manager.ordenar_por_saude(disponiveis)
    
    def get_chave_valida(self, provedor: str) -> Optional[str]:
        """Obtém próxima chave válida do provedor"""
        chaves = self.chaves_por_provedor.get(provedor, [])
        if not chaves:
            return None
        
        tentativas = 0
        while tentativas < len(chaves):
            idx = self.indice_chaves[provedor] % len(chaves)
            chave = chaves[idx]
            
            # Verificar se chave não falhou recentemente (última hora)
            falha_em = self.chaves_falhas[provedor].get(chave, 0)
            if (datetime.now().timestamp() - falha_em) > 3600:
                return chave
            
            self.indice_chaves[provedor] = (self.indice_chaves[provedor] + 1) % len(chaves)
            tentativas += 1
        
        return None
    
    def marcar_chave_falha(self, provedor: str, chave: str):
        """Marca chave como falha temporária"""
        self.chaves_falhas[provedor][chave] = datetime.now().timestamp()
        self.indice_chaves[provedor] = (self.indice_chaves[provedor] + 1) % len(self.chaves_por_provedor[provedor])
        
        health = self.health_manager.get_health(provedor)
        health.registrar_erro("chave_invalida")
    
    def marcar_provedor_offline(self, provedor: str, motivo: str = ""):
        """Marca provedor como offline"""
        self.provedores_offline.add(provedor)
        print(f"🚫 Provedor {provedor} offline: {motivo}")
        
        # Reativação automática após 30 min
        asyncio.create_task(self._reativar_provedor(provedor, 1800))
    
    async def _reativar_provedor(self, provedor: str, delay: int):
        """Reativa provedor após delay"""
        await asyncio.sleep(delay)
        if provedor in self.provedores_offline:
            self.provedores_offline.remove(provedor)
            # Resetar health
            self.health_manager.health_por_provedor[provedor] = ProvedorHealth(nome=provedor)
            print(f"✅ Provedor {provedor} reativado")
    
    async def fazer_requisicao(self, session: aiohttp.ClientSession,
                               endpoint: str,
                               parametros: Dict,
                               provedor: str,
                               chave: str,
                               timeout: int = 15) -> Tuple[Optional[Dict], float]:
        """
        Executa requisição com medição de latência e registro de saúde
        Retorna: (dados, latencia_ms)
        """
        health = self.health_manager.get_health(provedor)
        
        inicio = datetime.now()
        
        try:
            url = f"{self.urls_base.get(provedor, '')}/{endpoint}"
            params = {**parametros, "apiKey": chave} if "apiKey" not in parametros else parametros
            
            async with session.get(url, params=params, timeout=timeout) as r:
                latencia = (datetime.now() - inicio).total_seconds() * 1000
                
                if r.status == 200:
                    dados = await r.json()
                    health.registrar_sucesso(latencia)
                    return dados, latencia
                else:
                    health.registrar_erro(f"http_{r.status}")
                    return None, latencia
                    
        except asyncio.TimeoutError:
            health.registrar_erro("timeout")
            return None, (datetime.now() - inicio).total_seconds() * 1000
        except Exception as e:
            health.registrar_erro(f"exception_{type(e).__name__}")
            return None, (datetime.now() - inicio).total_seconds() * 1000
    
    def get_relatorio_saude(self) -> str:
        """Gera relatório completo de saúde"""
        return self.health_manager.get_relatorio()


# ==========================================
# FUNÇÕES UTILITÁRIAS
# ==========================================

def normalizar_nome(nome: str) -> str:
    """Normaliza nome para comparação"""
    import unicodedata
    if not isinstance(nome, str):
        return str(nome)
    return ''.join(
        c for c in unicodedata.normalize('NFD', nome)
        if unicodedata.category(c) != 'Mn'
    ).lower().strip()


class RateLimiter:
    """Controla rate limiting global"""
    
    def __init__(self, delay_seconds: float = 1.5):
        self.delay = delay_seconds
        self.ultimo_request = 0
        self.lock = asyncio.Lock()
    
    async def wait(self):
        """Aguarda tempo necessário entre requisições"""
        async with self.lock:
            agora = datetime.now().timestamp()
            tempo_passado = agora - self.ultimo_request
            if tempo_passado < self.delay:
                await asyncio.sleep(self.delay - tempo_passado)
            self.ultimo_request = datetime.now().timestamp()


# Rate limiter global
rate_limiter = RateLimiter()

# ==========================================
# CONFIGURAÇÕES DE CHAVES (para importação)
# ==========================================

CHAVES_PADRAO = {
    "odds_api": [
        "6249ca36b148b2542bb433d23e4ace65a97c896b7dc3b93c79b4a6715b29ea7d",
        "b29dcd347f5f26ddebb469eaa9e5f98fb75ca20be03cc47117027604d0a9f029",
        "528e79310c9161f769a282b8d2aa61be2bb332e0cc036a51e44acee5ca7bd66f"
    ],
    "sgo": ["e38185eb8b9eff32802ff016db544dc3"],
    "the_odds_token": [
        "b668851102c3e0a56c33220161c029ec",
        "0d43575dd39e175ba670fb91b2230442",
        "d32378e66e89f159688cc2239f38a6a4",
        "713146de690026b224dd8bbf0abc0339"
    ],
    "the_odds_api_legacy": [
        "6a1c0078b3ed09b42fbacee8f07e7cc3",
        "4949c49070dd3eff2113bd1a07293165",
        "0ecb237829d0f800181538e1a4fa2494",
        "4790419cc795932ffaeb0152fa5818c8",
        "5ee1c6a8c611b6c3d6aff8043764555f",
        "b668851102c3e0a56c33220161c029ec",
        "0d43575dd39e175ba670fb91b2230442",
        "d32378e66e89f159688cc2239f38a6a4",
        "713146de690026b224dd8bbf0abc0339"
    ],
    "api_football": [
        "da86ad79bf29f8ec19e1addb90247771",
        "4671a78ca6443a7970d2ed8efe4cbdba",
        "54e4ec4343a1abe56fe74a2eabc58ff7"
    ],
    "sportmonks": ["J2b3qS2pn660ss8pJUhTijsHHMmbDPQuxN3rnHhO7nnsUrI8qctzpla1LwQU"],
    "balldontlie": [
        "a8d9ab5d-7c93-469a-8c3a-924fd4e5e7b4",
        "8033f045-a2b3-47c6-919a-9141145c742c",
        "3ddaee43-d801-4559-84fd-e233e8f4bb9c",
        "afaca1cf-3bbe-47cc-93f5-6e7a1adfd195",
        "d1559bc7-3ceb-4c0d-8171-0d2298988cf5"
    ],
    "sportsdb": [
        "f8W9DfG71LPWMeU2TxkMtK1PEmWVwGzWW2B1Lmk9",
        "z7Dzdk5NlGtFvg5SqfL1IZWGkjOkXnOsv7tiPRrS",
        "ftAAx0FNerTm0lFMxFnWmxEbFKn7BSEMF83yosTf",
        "w1SolKpreujO7wmAKJmrW1lvfB7zK3Vv6ORnFc1t"
    ]
}

TELEGRAM_TOKENS = {
    "bot1": "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A",
    "bot2": "8185027087:AAH1JQJKtlWy_oUQpAvqvHEsFIVOK3ScYBc",
    "bot3": "8413563055:AAGyovCDMJOxiAukTbXwaJPm3ZDckIf7qJU"
}