from apscheduler.schedulers.background import BackgroundScheduler

from services.probium_v2_pro_scanner import run_probium_v2_pro
from services.telegram_bot import send_message


scheduler = BackgroundScheduler()


def scan_job():

    bets = run_probium_v2_pro()

    if not bets:
        print("Nenhuma aposta encontrada")
        return

    msg = "📊 PROBIUM V2 PRO\n\n"

    for b in bets:

        msg += f"⚽ {b.home} x {b.away}\n"
        msg += f"📈 {b.market} @ {b.odd}\n"
        msg += f"EV: {round(b.ev*100,2)}%\n\n"

    send_message(msg)

    print("Scanner V2 PRO executado")


def start_scheduler(app):

    scheduler.add_job(
        scan_job,
        "cron",
        hour="9,14,18,21"
    )

    scheduler.start()

    print("🤖 Scheduler iniciado - PROBIUM V2 PRO")