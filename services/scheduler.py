from threading import Thread
from services.match_scanner import start_scanner

def start_scheduler():

    scanner_thread = Thread(target=start_scanner)

    scanner_thread.daemon = True

    scanner_thread.start()