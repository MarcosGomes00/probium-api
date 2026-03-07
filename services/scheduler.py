import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import pytz
from sqlalchemy import text

from config import Config
from services.database import db
from services.probium_pipeline import motor_deep_analysis_diario
from services.telegram_bot import envia_alerta_pre_jogo, disparar_dashboard_bot2, fechar_operacao_resolvida

tz_br = pytz.timezone('America/Sao_Paulo')

# --- Função Matinal (Agenda os alarmes) ---
def organizar_bilhetes_do_dia():
    print("Buscando pérolas do dia...")
    melhores_entradas = motor_deep_analysis_diario()
    
    if not melhores_entradas:
        print("Nenhuma pérola validada pra hoje.")
        return
        
    agora = datetime.now(tz_br)
    for entrada in melhores_entradas:
        # Extrai a data "YYYY-MM-DDTHH:MM" fornecida pela API e calcula Menos 30 minutos
        data_formatada = datetime.fromisoformat(entrada['horario']).astimezone(tz_br)
        tempo_disparo = data_formatada - timedelta(minutes=30)
        
        if tempo_disparo > agora:
            # Deixa agendado na memória para enviar 30m antes do jogo explodir!
            agendador.add_job(envia_alerta_pre_jogo, DateTrigger(run_date=tempo_disparo), args=[entrada])
            print(f"Agenda Criada! Enviaremos aposta de {entrada['jogo']} as {tempo_disparo.strftime('%H:%M')}")

# --- Bot 2: Validador de Auditoria (Após o jogo terminar) ---
def rotina_validacao_finalizada(app):
    print("Bot 2 buscando partidas terminadas no Banco de Dados...")
    headers = {"x-apisports-key": Config.API_FOOTBALL_KEY}
    
    with app.app_context():
        with db.engine.connect() as conn:
            # Procura os que eu avisei antes e agora devem estar finalizados (FT)
            pendentes = conn.execute(text("SELECT id, fixture_id, jogo, mercado_tipo, odd FROM operacoes_tipster WHERE status = 'PENDENTE'")).fetchall()
            
            for row in pendentes:
                url = f"https://v3.football.api-sports.io/fixtures?id={row.fixture_id}"
                jogo_data = requests.get(url, headers=headers).json().get("response", [])
                if not jogo_data: continue
                
                match = jogo_data[0]
                status = match["fixture"]["status"]["short"]
                
                # "FT" = Match Finished, "AET" = Finished after extra time
                if status in ["FT", "AET", "PEN"]:
                    gh, ga = match["goals"]["home"], match["goals"]["away"]
                    mercado = row.mercado_tipo
                    resultado_resolvido = 'RED'
                    
                    # A Validação oficial Matemática:
                    if mercado == 'HOME' and gh > ga: resultado_resolvido = 'GREEN'
                    elif mercado == 'OVER25' and (gh + ga) > 2.5: resultado_resolvido = 'GREEN'
                    elif mercado == 'BTTS' and gh > 0 and ga > 0: resultado_resolvido = 'GREEN'
                    
                    # Dá o Update no DB para não processar de novo:
                    conn.execute(text(f"UPDATE operacoes_tipster SET status = '{resultado_resolvido}' WHERE id = {row.id}"))
                    conn.commit()
                    
                    # Dispara Bot 2 Avisando Green ou Red e atualiza Grupo Dashboard!
                    fechar_operacao_resolvida(row.jogo, mercado, resultado_resolvido, row.odd)
                    
            # Quando termina a varredura, solta o extrato geral vitalício:
            if pendentes:
                disparar_dashboard_bot2()

# --- Configuração Master ---
agendador = BackgroundScheduler()

def start_scheduler(app):
    # Agendador Matinal 1: Todo dia as 08:00 BR analisa as oportunidades e programa os Disparos para os -30Min
    agendador.add_job(organizar_bilhetes_do_dia, CronTrigger(hour=8, minute=0, timezone=tz_br))
    
    # Validador Bot 2: Todo dia varre os finalizados para lançar Greens (a cada 4h horas, p. ex)
    agendador.add_job(rotina_validacao_finalizada, 'interval', hours=4, args=[app])
    
    agendador.start()
    print("Módulo Duplo Tipster IA Incializado! Rotinas armadas para operar automaticamente 24/7.")