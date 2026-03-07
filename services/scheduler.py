from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from services.probium_pipeline import analisar_jogos_e_gerar_bilhetes
from services.telegram_bot import mandar_analises_para_grupo

def rotina_automatica_das_15h30():
    print("Gatilho das 15:30 ativado. Iniciando operações analíticas...")
    analises = analisar_jogos_e_gerar_bilhetes()
    mandar_analises_para_grupo(analises)
    print("Rotina analítica diária concluída.")

def start_scheduler(app):
    scheduler = BackgroundScheduler()
    fuso_horario_br = pytz.timezone("America/Sao_Paulo")
    
    # Configuração para rodar diariamente às 15:30 rigorosamente.
    scheduler.add_job(
        func=rotina_automatica_das_15h30, 
        trigger=CronTrigger(hour=15, minute=30, timezone=fuso_horario_br),
        id='job_operacao_principal'
    )
    
    scheduler.start()
    print("Automação configurada. O sistema disparará as análises todos os dias às 15:30 (Horário de Brasília).")