import asyncio
import aiohttp
import time
import json
import sqlite3
import unicodedata
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

API_KEYS_ODDS =[
"6a1c0078b3ed09b42fbacee8f07e7cc3",
"4949c49070dd3eff2113bd1a07293165",
"0ecb237829d0f800181538e1a4fa2494",
"4790419cc795932ffaeb0152fa5818c8",
"5ee1c6a8c611b6c3d6aff8043764555f",
"b668851102c3e0a56c33220161c029ec",
"0d43575dd39e175ba670fb91b2230442",
"d32378e66e89f159688cc2239f38a6a4",
"713146de690026b224dd8bbf0abc0339"
]

TELEGRAM_TOKEN = "8725909088:AAGQMNr-9RVQB7hWmePCLmm0GwaGuzOVy-A"
CHAT_ID = "-1003814625223"
DB_FILE = "probum.db"

SOFT_BOOKIES =["bet365","betano","1xbet","draftkings","williamhill","unibet","888sport","betfair_ex_eu"]
SHARP_BOOKIE="pinnacle"
TODAS_CASAS=SOFT_BOOKIES+[SHARP_BOOKIE]

SCAN_INTERVAL=18000

LIGAS=[
"soccer_epl",
"soccer_spain_la_liga",
"soccer_italy_serie_a",
"soccer_germany_bundesliga",
"soccer_france_ligue_one",
"soccer_portugal_primeira_liga",
"soccer_uefa_champs_league",
"soccer_uefa_europa_league",
"soccer_brazil_campeonato",
"soccer_brazil_copa_do_brasil",
"soccer_brazil_serie_b",
"soccer_conmebol_copa_libertadores",
"soccer_conmebol_copa_sudamericana",
"basketball_nba",
"basketball_euroleague"
]

jogos_enviados={}
historico_pinnacle={}
memoria_ia={}
chave_odds_atual=0
api_lock=asyncio.Lock()

oportunidades_globais=[]

limite_por_esporte={
"soccer":6,
"basketball":2
}

def inicializar_banco():
 conn=sqlite3.connect(DB_FILE)
 cursor=conn.cursor()
 cursor.execute("""
 CREATE TABLE IF NOT EXISTS operacoes_tipster(
 id_aposta TEXT PRIMARY KEY,
 esporte TEXT,
 jogo TEXT,
 liga TEXT,
 mercado TEXT,
 selecao TEXT,
 odd REAL,
 prob REAL,
 ev REAL,
 stake REAL,
 status TEXT DEFAULT 'PENDENTE',
 lucro REAL DEFAULT 0,
 data_hora TEXT
 )
 """)
 conn.commit()
 conn.close()

async def enviar_telegram_async(session,texto):
 url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
 payload={"chat_id":CHAT_ID,"text":texto,"parse_mode":"HTML","disable_web_page_preview":True}
 try:
  await session.post(url,json=payload,timeout=10)
 except:
  pass

async def fazer_requisicao_odds(session,url,parametros):
 global chave_odds_atual
 for _ in range(len(API_KEYS_ODDS)):
  async with api_lock:
   chave=API_KEYS_ODDS[chave_odds_atual]

  parametros["apiKey"]=chave
  try:
   async with session.get(url,params=parametros,timeout=15) as r:
    if r.status==200:
     return await r.json()

    if r.status in[401,429]:
     async with api_lock:
      chave_odds_atual=(chave_odds_atual+1)%len(API_KEYS_ODDS)
  except:
   pass

 return None

def normalizar_nome(nome):
 if not isinstance(nome,str):
  return str(nome)

 nome=''.join(c for c in unicodedata.normalize('NFD',nome) if unicodedata.category(c)!='Mn').lower().strip()

 sufixos=[" fc"," cf"," cd"," sc"," cp"," fk"," nk"]
 for s in sufixos:
  if nome.endswith(s):
   nome=nome[:-len(s)].strip()

 mapa={
 "bayern munich":"bayern",
 "bayern munchen":"bayern",
 "paris saint germain":"psg",
 "paris sg":"psg",
 "internazionale":"inter",
 "inter milan":"inter",
 "ac milan":"milan"
 }

 return mapa.get(nome,nome)

def calcular_prob_justa(outcomes):
 try:
  margem=sum(1/i["price"] for i in outcomes if i["price"]>0)
  return {normalizar_nome(i["name"]):(1/i["price"])/margem for i in outcomes if i["price"]>0}
 except:
  return {}

def validar_com_ia(odd,prob,ev):

 if not(1.30<=odd<=15):
  return False

 if ev>0.18:
  return False

 if odd<=1.7:
  ev_min=0.01
 elif odd<=3.5:
  ev_min=0.02
 else:
  ev_min=0.035

 return ev>=ev_min

def classificar_aposta(ev,odd,steam):

 if steam:
  return "OPORTUNIDADE"

 if ev>=0.08:
  return "SNIPER"

 if ev>=0.04:
  return "MODERADA"

 return "NORMAL"

async def processar_liga_async(session,liga,agora):

 is_nba="basketball" in liga

 mercados="h2h,spreads,totals" if is_nba else "h2h,btts,spreads,totals"

 parametros={
 "regions":"eu",
 "markets":mercados,
 "bookmakers":",".join(TODAS_CASAS)
 }

 url=f"https://api.the-odds-api.com/v4/sports/{liga}/odds/"

 data=await fazer_requisicao_odds(session,url,parametros)

 if not data:
  return

 for evento in data:

  jogo_id=str(evento["id"])

  if jogo_id in jogos_enviados:
   continue

  horario=datetime.fromisoformat(evento["commence_time"].replace("Z","+00:00")).astimezone(ZoneInfo("America/Sao_Paulo"))

  minutos=(horario-agora).total_seconds()/60

  if not(15<=minutos<=1440):
   continue

  bookmakers=evento.get("bookmakers",[])

  pinnacle=next((b for b in bookmakers if b["key"]==SHARP_BOOKIE),None)

  if not pinnacle:
   continue

  oportunidades_jogo=[]

  for soft in bookmakers:

   if soft["key"]==SHARP_BOOKIE or soft["key"] not in SOFT_BOOKIES:
    continue

   for mercado in soft.get("markets",[]):

    pin_m=next((m for m in pinnacle["markets"] if m["key"]==mercado["key"]),None)

    if not pin_m:
     continue

    probs=calcular_prob_justa(pin_m["outcomes"])

    for out in mercado["outcomes"]:

     nome=normalizar_nome(out["name"])

     prob=probs.get(nome)

     if not prob:
      continue

     odd=out["price"]

     ev=(prob*odd)-1

     if not validar_com_ia(odd,prob,ev):
      continue

     oportunidades_jogo.append({
     "jogo_id":jogo_id,
     "evento":evento,
     "home_team":evento["home_team"],
     "away_team":evento["away_team"],
     "mercado_nome":mercado["key"],
     "selecao_nome":out["name"],
     "odd_bookie":odd,
     "prob_justa":prob,
     "ev_real":ev,
     "nome_bookie":soft["title"],
     "horario":horario,
     "minutos":minutos,
     "esporte":"basketball" if is_nba else "soccer"
     })

  if oportunidades_jogo:
   melhor=max(oportunidades_jogo,key=lambda x:x["ev_real"])
   oportunidades_globais.append(melhor)

async def gerenciar_varreduras_e_enviar():

 global oportunidades_globais

 agora=datetime.now(ZoneInfo("America/Sao_Paulo"))

 oportunidades_globais.clear()

 async with aiohttp.ClientSession() as session:

  tarefas=[processar_liga_async(session,l,agora) for l in LIGAS]

  await asyncio.gather(*tarefas)

  if not oportunidades_globais:
   return

  oportunidades_globais.sort(key=lambda x:x["ev_real"],reverse=True)

  contagem={"soccer":0,"basketball":0}

  for op in oportunidades_globais:

   esporte=op["esporte"]

   if contagem[esporte]>=limite_por_esporte[esporte]:
    continue

   contagem[esporte]+=1

   odd=op["odd_bookie"]
   ev=op["ev_real"]

   tipo=classificar_aposta(ev,odd,False)

   if tipo=="OPORTUNIDADE":
    cabecalho="🔥 <b>OPORTUNIDADE ÚNICA</b>"
   elif tipo=="SNIPER":
    cabecalho="🎯 <b>SNIPER INSTITUCIONAL</b>"
   elif tipo=="MODERADA":
    cabecalho="💎 <b>ENTRADA MODERADA</b>"
   else:
    cabecalho="📊 <b>VALUE BET</b>"

   horas=int(op["minutos"]//60)
   mins=int(op["minutos"]%60)

   tempo=f"{horas}h {mins}min" if horas>0 else f"{mins} min"

   texto=(
   f"{cabecalho}\n\n"
   f"🏆 <b>Liga:</b> {op['evento']['sport_title']}\n"
   f"⏰ <b>Horário:</b> {op['horario'].strftime('%H:%M')} (Faltam {tempo})\n"
   f"⚽ <b>Jogo:</b> {op['home_team']} x {op['away_team']}\n\n"
   f"🎯 <b>Mercado:</b> {op['mercado_nome']}\n"
   f"👉 <b>Entrada:</b> {op['selecao_nome']}\n"
   f"🏛️ <b>Casa de Aposta:</b> {op['nome_bookie']}\n"
   f"📈 <b>Odd Atual:</b> {odd:.2f}\n\n"
   f"💰 <b>Gestão/Stake:</b> 1.0% Unidades\n"
   f"🛡️ <b>Confiança:</b> FORTE\n"
   f"📊 <b>Vantagem Matemática (+EV):</b> +{ev*100:.2f}%\n"
   f"✅ <b>Probabilidade Real:</b> {op['prob_justa']*100:.1f}%"
   )

   await enviar_telegram_async(session,texto)

   jogos_enviados[op["jogo_id"]]=datetime.now()+timedelta(hours=24)

async def loop_infinito():

 while True:

  print("\n🔎 VARREDURA GERAL INICIADA")

  await gerenciar_varreduras_e_enviar()

  print("\n⏳ Bot dormindo por 5 horas...")

  await asyncio.sleep(SCAN_INTERVAL)

if __name__=="__main__":

 inicializar_banco()

 print("🤖 BOT SINDICATO ASIÁTICO V11 PRO INICIADO")

 asyncio.run(loop_infinito())