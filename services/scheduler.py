from apscheduler.schedulers.background import BackgroundScheduler

from services.probium_pipeline import run_pipeline
from services.reports.daily_report import generate_report


scheduler = BackgroundScheduler()


def start_scheduler(app):

    print("🚀 Scheduler iniciado")

    # ===============================
    # SCANNER DE JOGOS
    # ===============================

    scheduler.add_job(
        run_pipeline,
        "interval",
        minutes=5,
        id="scan_matches",
        replace_existing=True
    )

    # ===============================
    # RELATÓRIO DIÁRIO
    # ===============================

    scheduler.add_job(
        generate_report,
        "cron",
        hour=23,
        minute=0,
        id="daily_report",
        replace_existing=True
    )

    scheduler.start()

    print("✅ Scheduler ativo")