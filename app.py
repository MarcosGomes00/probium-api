# CRIAR TABELA DO BOT DE VALIDAÇÃO (HISTÓRICO A LONGO PRAZO)
with app.app_context():
    db.engine.execute(text("""
    CREATE TABLE IF NOT EXISTS operacoes_tipster (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fixture_id INTEGER,
        jogo TEXT,
        data_hora TEXT,
        mercado_tipo TEXT,  -- Ex: "HOME", "OVER25", "BTTS"
        odd REAL,
        status TEXT DEFAULT 'PENDENTE', -- Muda pra 'GREEN' ou 'RED' depois
        id_mensagem_telegram INTEGER
    )
    """))