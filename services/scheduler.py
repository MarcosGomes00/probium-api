
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio
from services.analysis_generator import AnalysisGenerator
from services.telegram_bot import telegram_service

scheduler = BackgroundScheduler()

def daily_job():

    analyses = AnalysisGenerator().generate_daily()

    formatted = []

    for a in analyses:

        formatted.append({
            "home_team":a.home_team,
            "away_team":a.away_team,
            "league":a.league,
            "odds":a.odds,
            "probability_ai":a.probability_ai,
            "confidence":a.confidence,
            "market":a.market
        })

    asyncio.run(
        telegram_service.send_top10(formatted)
    )

def start_scheduler():

    scheduler.add_job(
        daily_job,
        "cron",
        hour=8,
        minute=30
    )

    scheduler.start()
