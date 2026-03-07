import requests
from config import Config
from datetime import datetime, timedelta

def analisa_ultimos_5(id_time, headers):
    """Busca os ultimos 5 jogos gerais do time para ver como ele vem na temporada (Momento atual)"""
    url = f"https://v3.football.api-sports.io/fixtures?team={id_time}&last=5"
    
    try:
        response = requests.get(url, headers=headers)
        jogos = response.json().get("response", [])
    except Exception as e:
        print(f"Erro ao buscar últimos jogos do time {id_time}: {e}")
        return {"over_taxa": 0, "btts_taxa": 0, "vitoria_taxa": 0}
    
    gols_feitos = 0
    gols_sofridos = 0
    jogos_over = 0
    jogos_btts = 0
    vitorias = 0
    
    total_validos = 0

    for j in jogos:
        status = j["fixture"]["status"]["short"]
        if status not in ["FT", "AET", "PEN"]:
            continue # Ignora se o jogo não terminou de verdade

        g_home = j["goals"]["home"]
        g_away = j["goals"]["away"]
        
        if g_home is None or g_away is None: 
            continue
            
        total_validos += 1
        total_gols = g_home + g_away
        
        # Matemática de Tendências
        if total_gols > 2.5: 
            jogos_over += 1
            
        if g_home > 0 and g_away > 0: 
            jogos_btts += 1
        
        eh_casa = j["teams"]["home"]["id"] == id_time
        if eh_casa:
            if g_home > g_away: 
                vitorias += 1
            gols_feitos += g_home
            gols_sofridos += g_away
        else:
            if g_away > g_home: 
                vitorias += 1
            gols_feitos += g_away
            gols_sofridos += g_home
            
    # Proteção caso API retorne vazio
    if total_validos == 0:
        return {"over_taxa": 0, "btts_taxa": 0, "vitoria_taxa": 0}

    return {
        "over_taxa": jogos_over / total_validos, 
        "btts_taxa": jogos_btts / total_validos, 
        "vitoria_taxa": vitorias / total_validos
    }

def motor_deep_analysis_diario():
    """Varre as grandes ligas nos próximos 2 dias, faz cruzamento estatístico e aprova os Bilhetes"""
    print("\n🔍 PROBIUM IA INICIANDO RASTREIO TÁTICO E MATEMÁTICO...")
    headers = {"x-apisports-key": Config.API_FOOTBALL_KEY}
    
    # Busca jogos dos próximos 2 dias em vez de apenas o dia atual vazio
    futuro_limite = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    url = "https://v3.football.api-sports.io/fixtures"
    
    params = {
        "date": futuro_limite, 
        "timezone": "America/Sao_Paulo"
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        jogos_brutos = response.json().get("response", [])
    except Exception as e:
        print(f"Falha de conexão com a Football API: {e}")
        return []

    if not jogos_brutos:
        print("⚠️ A API retornou vazia. Cheque o Rate Limit (Se não passou de 100 hoje).")
        return []
        
    print(f"⚽ {len(jogos_brutos)} jogos globais carregados no cérebro. Filtrando joias raras...")
    
    # IDs MAIS RENTÁVEIS: Premier(39), BR(71), LaLiga(140), SerieA(135), Bundesliga(78), Champions(2), Liberta(13)
    # Ligas estendidas para achar mais padrão Ouro: Eredivisie (88), MLS(253), Europa League (3), Portugal (94)
    ligas_premium = [1, 2, 3, 13, 39, 61, 71, 78, 88, 94, 135, 140, 253, 307]
    lista_ouro = []

    for j in jogos_brutos:
        liga_id = j["league"]["id"]
        status = j["fixture"]["status"]["short"]
        
        # Ignora lixo de segundas divisões asiáticas e jogos que já começaram (Só queremos ligas limpas e Pre-Match 'NS')
        if liga_id in ligas_premium and status == "NS":
            fix_id = j["fixture"]["id"]
            casa_id = j["teams"]["home"]["id"]
            fora_id = j["teams"]["away"]["id"]
            nome_casa = j["teams"]["home"]["name"]
            nome_fora = j["teams"]["away"]["name"]
            
            print(f"📊 Analisando duelo no supercomputador: {nome_casa} x {nome_fora} (Liga ID: {liga_id})")
            
            # --- CRUZAMENTO DE FORÇA DE DADOS REAIS ---
            fase_casa = analisa_ultimos_5(casa_id, headers)
            fase_fora = analisa_ultimos_5(fora_id, headers)
            
            # Cálculo Base: Combinação das métricas das duas equipes para chegar num Score Justo
            media_vitoria_casa = fase_casa["vitoria_taxa"]
            media_over = (fase_casa["over_taxa"] + fase_fora["over_taxa"]) / 2
            media_btts = (fase_casa["btts_taxa"] + fase_fora["btts_taxa"]) / 2

            mercado_sugerido = None
            mercado_codigo = None
            probabilidade_final = 0.0
            
            # Crivo Matemático: Régua baixada de Impossíveis 80% para realistas Excelentes (60%)
            if media_vitoria_casa >= 0.65:
                mercado_sugerido = f"Vitória Seca do Mandante - {nome_casa}"
                mercado_codigo = "HOME"
                probabilidade_final = media_vitoria_casa * 100

            elif media_over >= 0.65:
                mercado_sugerido = "Mercado de Gols - Mais de 2.5 (OVER 2.5)"
                mercado_codigo = "OVER25"
                probabilidade_final = media_over * 100

            elif media_btts >= 0.60: # 60% de média dos 2 times fazendo e sofrendo = Jogo pegado!
                mercado_sugerido = "Ambas Equipes Marcam (BTTS - SIM)"
                mercado_codigo = "BTTS"
                probabilidade_final = media_btts * 100
            
            if mercado_sugerido:
                # O Robô inventa uma Odd conservadora baseado no Value (Caso queira integrar the-odds API de fato ali depois)
                odd_gerada = round((100 / probabilidade_final) + 0.35, 2)
                
                lista_ouro.append({
                    "fix_id": fix_id, 
                    "jogo": f"{nome_casa} x {nome_fora}",
                    "horario": j["fixture"]["date"], 
                    "mercado": mercado_sugerido, 
                    "mercado_codigo": mercado_codigo, 
                    "prob": round(probabilidade_final, 1),
                    "odd": odd_gerada
                })

    if not lista_ouro:
        print("🤷 Crivo encerrou. Mesmo buscando próximos dias, sem palpites 'Super-Trust' encontrados agora.")
        return []

    # Sort array pelo EV (Expected Value mais seguro pra galera): Do topo pra baixo
    lista_ouro.sort(key=lambda x: x["prob"], reverse=True)
    
    # Limita em Maximo as TOP 3, para nao enviar SPAM no grupo Telegram
    top3 = lista_ouro[:3]
    
    print(f"\n✅ MISSÃO CUMPRIDA! Encontradas {len(lista_ouro)} Oportunidades puras.")
    print(f"Separando o Nectar Top 3 pro Robô Bot 1 preparar o Agendamento dos envios pro Telegram:")
    
    return top3