from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

from services.probium_pipeline import run_pipeline
from services.result_checker import check_results


scheduler = BackgroundScheduler()


def run_scanner():

    print("\n🤖 PROBIUM AI SCANNER EXECUTANDO")

    try:

        run_pipeline()

        print("✅ Scanner finalizado", datetime.now())

    except Exception as e:

        print("❌ Erro no scanner:", e)


def run_results():

    print("\n📊 VERIFICANDO RESULTADOS DAS APOSTAS")

    try:

        check_results()

        print("✅ Resultados atualizados", datetime.now())

    except Exception as e:

        print("❌ Erro ao verificar resultados:", e)


def start_scheduler(app):

    print("\n🚀 Scheduler iniciado - PROBIUM AI")

    # scans principais do dia
    scheduler.add_job(run_scanner, "cron", hour=9, minute=0)
    scheduler.add_job(run_scanner, "cron", hour=14, minute=0)
    scheduler.add_job(run_scanner, "cron", hour=18, minute=0)
    scheduler.add_job(run_scanner, "cron", hour=21, minute=0)

    # verificação de resultados
    scheduler.add_job(run_results, "cron", hour=23, minute=30)

    scheduler.start()