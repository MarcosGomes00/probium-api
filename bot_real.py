def processar_jogos_e_enviar():
    agora_br = datetime.now(ZoneInfo("America/Sao_Paulo"))
    print(f"\n🔄[ATUALIZAÇÃO - {agora_br.strftime('%H:%M:%S')}] Escaneando Valor Global...")
    
    # ---------------------------------------------------------
    # NOVO: Lista para guardar TODAS as oportunidades do momento
    # ---------------------------------------------------------
    oportunidades_globais =[]
    LIMITE_POR_VARREDURA = 3 # <-- Mude aqui para quantas dicas quer receber por vez
    
    for liga in LIGAS:
        time.sleep(1) # Previne erro 429 da API
        is_nba = "basketball" in liga
        mercados_alvo = "h2h,spreads,totals" if is_nba else "h2h,btts,totals,draw_no_bet,double_chance"
        
        casas_busca = f"{SHARP_BOOKIE}," + ",".join(SOFT_BOOKIES)
        parametros = {"regions": "eu,us", "markets": mercados_alvo, "bookmakers": casas_busca}
        url_odds = f"https://api.the-odds-api.com/v4/sports/{liga}/odds/"
        
        resposta = fazer_requisicao_odds(url_odds, parametros)
        if not resposta or resposta.status_code != 200: continue
            
        try:
            for evento in resposta.json():
                horario_br = datetime.fromisoformat(evento["commence_time"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Sao_Paulo"))
                minutos_faltando = (horario_br - agora_br).total_seconds() / 60
                
                # RECOMENDAÇÃO SNIPER: Apenas jogos das próximas 3 HORAS (180 min) a 24 HORAS
                if not (15 <= minutos_faltando <= 1440): continue 

                bookmakers = evento.get("bookmakers", [])
                pinnacle = next((b for b in bookmakers if b["key"] == SHARP_BOOKIE), None)
                if not pinnacle: continue 

                home_team, away_team = evento["home_team"], evento["away_team"]
                oportunidades_jogo =[]
                
                for soft_b in bookmakers:
                    if soft_b["key"] == SHARP_BOOKIE or soft_b["key"] not in SOFT_BOOKIES: continue
                    nome_casa = soft_b["title"]

                    # 1. MATCH ODDS
                    pin_h2h = next((m for m in pinnacle.get("markets",[]) if m["key"] == "h2h"), None)
                    soft_h2h = next((m for m in soft_b.get("markets",[]) if m["key"] == "h2h"), None)
                    if pin_h2h and soft_h2h:
                        probs_justas = calcular_prob_justa(pin_h2h["outcomes"])
                        for s_outcome in soft_h2h["outcomes"]:
                            prob_real = probs_justas.get(s_outcome["name"], 0)
                            odd_oferecida = s_outcome["price"]
                            if prob_real > 0 and (1.40 <= odd_oferecida <= 3.50): # Filtro de Odd Segura
                                ev_real = (prob_real * odd_oferecida) - 1
                                if ev_real >= 0.015: oportunidades_jogo.append(("Vencedor", s_outcome["name"], odd_oferecida, prob_real, ev_real, nome_casa))

                    # 2. BTTS
                    pin_btts = next((m for m in pinnacle.get("markets",[]) if m["key"] == "btts"), None)
                    soft_btts = next((m for m in soft_b.get("markets",[]) if m["key"] == "btts"), None)
                    if pin_btts and soft_btts:
                        probs_justas = calcular_prob_justa(pin_btts["outcomes"])
                        for s_outcome in soft_btts["outcomes"]:
                            prob_real = probs_justas.get(s_outcome["name"], 0)
                            odd_oferecida = s_outcome["price"]
                            if prob_real > 0 and (1.40 <= odd_oferecida <= 3.50):
                                ev_real = (prob_real * odd_oferecida) - 1
                                if ev_real >= 0.015: oportunidades_jogo.append(("Ambas Marcam", "Sim" if s_outcome["name"]=="Yes" else "Não", odd_oferecida, prob_real, ev_real, nome_casa))

                    # 3. TOTALS (OVER/UNDER)
                    pin_tot = next((m for m in pinnacle.get("markets", []) if m["key"] == "totals"), None)
                    soft_tot = next((m for m in soft_b.get("markets",[]) if m["key"] == "totals"), None)
                    if pin_tot and soft_tot:
                        for s_outcome in soft_tot["outcomes"]:
                            ponto = s_outcome.get("point")
                            pin_match = next((p for p in pin_tot["outcomes"] if p["name"] == s_outcome["name"] and p.get("point") == ponto), None)
                            if pin_match:
                                par_pinnacle = [p for p in pin_tot["outcomes"] if p.get("point") == ponto]
                                try:
                                    prob_real = (1 / pin_match["price"]) / sum(1 / i["price"] for i in par_pinnacle if i["price"] > 0)
                                    odd_oferecida = s_outcome["price"]
                                    if prob_real > 0 and (1.40 <= odd_oferecida <= 3.50):
                                        ev_real = (prob_real * odd_oferecida) - 1
                                        if ev_real >= 0.015: oportunidades_jogo.append(("Gols/Pontos", f"{s_outcome['name']} {ponto}", odd_oferecida, prob_real, ev_real, nome_casa))
                                except: pass

                if not oportunidades_jogo: continue
                
                # Pega a melhor oportunidade DESTE JOGO
                melhor_op = max(oportunidades_jogo, key=lambda x: x[4]) 
                mercado_nome, selecao_nome, odd_bookie, prob_justa, ev_real, nome_bookie = melhor_op

                # FILTRO FINAL: Ignora "Fake News / Lesões" (EV absurdo acima de 12%)
                if ev_real > 0.12: continue

                jogo_id = f"{evento['id']}_{mercado_nome}_{selecao_nome}"
                
                if jogo_id not in jogos_enviados:
                    # EM VEZ DE ENVIAR AGORA, GUARDA NA LISTA GLOBAL
                    oportunidades_globais.append({
                        "jogo_id": jogo_id,
                        "evento": evento,
                        "home_team": home_team, "away_team": away_team,
                        "horario_br": horario_br, "minutos_faltando": minutos_faltando,
                        "mercado_nome": mercado_nome, "selecao_nome": selecao_nome,
                        "odd_bookie": odd_bookie, "prob_justa": prob_justa, 
                        "ev_real": ev_real, "nome_bookie": nome_bookie,
                        "is_nba": is_nba, "liga": liga
                    })

        except Exception as e: 
            print(f"⚠️ Erro no processamento: {e}")

    # ==========================================
    # NOVO: RANQUEAMENTO E ENVIO (MODO SNIPER)
    # ==========================================
    if oportunidades_globais:
        # 1. Ordena a lista de oportunidades do MAIOR EV para o MENOR EV
        oportunidades_globais.sort(key=lambda x: x["ev_real"], reverse=True)
        
        # 2. Corta a lista pegando apenas as top X melhores (ex: 3 melhores)
        top_snipers = oportunidades_globais[:LIMITE_POR_VARREDURA]
        
        print(f"\n🎯 Achamos {len(oportunidades_globais)} oportunidades +EV. Disparando apenas as {len(top_snipers)} melhores!")

        for op in top_snipers:
            ev_real = op["ev_real"]
            prob_justa = op["prob_justa"]
            odd_bookie = op["odd_bookie"]
            
            cabecalho = "💎 <b>APOSTA INSTITUCIONAL (SNIPER)</b> 💎" if ev_real >= 0.025 else "🔥 <b>OPORTUNIDADE DE VALOR (MODERADA)</b> 🔥"
            
            # Kelly Criterion
            b_kelly = odd_bookie - 1
            q_kelly = 1 - prob_justa
            try: kelly_pct = max(0.5, min(((prob_justa - (q_kelly / b_kelly)) * 0.25) * 100, 3.0))
            except: kelly_pct = 1.0

            horas_f, min_f = int(op["minutos_faltando"] // 60), int(op["minutos_faltando"] % 60)
            tempo_str = f"{horas_f}h {min_f}min" if horas_f > 0 else f"{min_f} min"
            emoji = "🏀" if op["is_nba"] else "⚽"
            bloco_historico = f"\n{obter_historico_times(op['home_team'], op['away_team'])}" if not op["is_nba"] else ""
            
            texto_msg = (
                f"{cabecalho}\n\n"
                f"🏆 <b>Liga:</b> {op['evento']['sport_title']}\n"
                f"⏰ <b>Horário:</b> {op['horario_br'].strftime('%H:%M')} (Faltam {tempo_str})\n"
                f"{emoji} <b>Jogo:</b> {op['home_team']} x {op['away_team']}\n\n"
                f"🎯 <b>Mercado:</b> {op['mercado_nome']}\n"
                f"👉 <b>Entrada:</b> {op['selecao_nome']}\n"
                f"🏛️ <b>Casa de Aposta:</b> {op['nome_bookie']}\n"
                f"📈 <b>Odd Atual:</b> {odd_bookie:.2f}\n\n"
                f"💰 <b>Gestão Recomendada:</b> {kelly_pct:.1f}% da Banca\n"
                f"📊 <b>Vantagem (+EV):</b> +{ev_real*100:.2f}%\n"
                f"{bloco_historico}"
            )
            enviar_telegram(texto_msg)
            jogos_enviados.add(op["jogo_id"])

            salvar_aposta_sistema({
                "id": op["evento"]["id"], "sport_key": op["liga"], "home": op["home_team"], "away": op["away_team"],
                "league": op["evento"]['sport_title'], "market_chosen": op["mercado_nome"], "selecao": op["selecao_nome"],
                "odd": round(odd_bookie, 2), "prob": prob_justa, "ev": ev_real, "stake_perc": round(kelly_pct, 2),
                "date": op["horario_br"].strftime('%d/%m/%Y')
            })
            print(f"🚀 ✅ TIP ENVIADA: {op['home_team']} x {op['away_team']} | EV: +{ev_real*100:.2f}%")
    else:
        print("\n😴 Nenhuma oportunidade Sniper encontrada nesta rodada.")