import json
import os

HISTORY_FILE = "bets_history.json"

def is_league_profitable(league_name):
    """
    O robô lê o próprio histórico. Se ele já fez pelo menos 5 apostas 
    numa liga e a taxa de acerto (Win Rate) estiver abaixo de 40%, 
    ele entende que 'não está lendo bem' esse campeonato e bloqueia as apostas.
    """
    if not os.path.exists(HISTORY_FILE):
        return True # Se não tem histórico, aprova para começar a aprender

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            bets = json.load(f)
    except:
        return True

    total_bets = 0
    greens = 0

    for bet in bets:
        # Analisa apenas apostas dessa liga que já tiveram o resultado checado (GREEN/RED)
        if bet.get("league") == league_name and bet.get("checked") and bet.get("result"):
            total_bets += 1
            if bet.get("result") == "GREEN":
                greens += 1

    # Só pune a liga se ele já tiver uma base mínima de 5 jogos testados
    if total_bets >= 5:
        win_rate = (greens / total_bets) * 100
        if win_rate < 40.0:
            print(f"🧠 AUTO-APRENDIZADO: Evitando a liga '{league_name}'. Win Rate atual está muito baixo ({win_rate:.1f}%).")
            return False # Bloqueia a aposta!

    return True # Aprovado!