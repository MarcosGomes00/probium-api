from services.match_scanner_definitivo import get_matches

matches = get_matches()

print("\nALGUNS JOGOS ENCONTRADOS\n")

for m in matches[:10]:

    print(m["home"], "x", m["away"], "-", m["league"])