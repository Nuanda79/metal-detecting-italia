#!/usr/bin/env python3
"""
Offerte Amazon per Metal Detecting Italia.

Legge una libreria di prodotti (nome, link affiliato, descrizione opzionale)
da un file CSV, ne sceglie alcuni a rotazione ogni giorno (in modo che in un
ciclo completo vengano proposti tutti prima di ripetersi), e genera il post
Markdown pronto per Hugo.

Formato del file prodotti.csv (separatore ';'):
    Nome Prodotto;https://www.amazon.it/dp/XXXX?tag=iltuotag-21;Descrizione breve (opzionale)

Se la descrizione è vuota, viene generata automaticamente da Gemini.

Uso:
    export GEMINI_API_KEY="la-tua-chiave"   (solo se alcune descrizioni sono vuote)
    python amazon_offers.py
"""

import os
import sys
import csv
import datetime

# ---------------------------------------------------------------------------
# CONFIGURAZIONE
# ---------------------------------------------------------------------------

PRODOTTI_FILE = "scripts/prodotti.csv"
N_PRODOTTI_AL_GIORNO = 3
OUTPUT_DIR = "content/offerte"


# ---------------------------------------------------------------------------
# STEP 1: LEGGI LA LIBRERIA PRODOTTI
# ---------------------------------------------------------------------------

def leggi_prodotti():
    if not os.path.exists(PRODOTTI_FILE):
        print(f"ERRORE: file '{PRODOTTI_FILE}' non trovato.")
        print("Crealo con righe nel formato: Nome;Link;Descrizione (opzionale)")
        sys.exit(1)

    prodotti = []
    contenuto = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(PRODOTTI_FILE, "r", encoding=encoding) as f:
                contenuto = f.read()
            break
        except UnicodeDecodeError:
            continue

    if contenuto is None:
        print("ERRORE: impossibile leggere il file con nessuna codifica nota.")
        sys.exit(1)

    reader = csv.reader(contenuto.splitlines(), delimiter=";")
    for riga in reader:
        if not riga or riga[0].strip().startswith("#"):
            continue  # righe vuote o commenti
        nome = riga[0].strip()
        link = riga[1].strip() if len(riga) > 1 else ""
        descrizione = riga[2].strip() if len(riga) > 2 else ""
        if nome and link:
            prodotti.append({"nome": nome, "link": link, "descrizione": descrizione})

    if not prodotti:
        print("ERRORE: nessun prodotto valido trovato nel file.")
        sys.exit(1)

    return prodotti


# ---------------------------------------------------------------------------
# STEP 2: SCEGLI I PRODOTTI DI OGGI (A ROTAZIONE, NON A CASO)
# ---------------------------------------------------------------------------

def scegli_prodotti_oggi(prodotti):
    n = len(prodotti)
    k = min(N_PRODOTTI_AL_GIORNO, n)

    # Usiamo il numero di giorni trascorsi (data ordinale) per calcolare un
    # indice di partenza stabile: cambia ogni giorno, e in un ciclo completo
    # (n // k giorni circa) tutti i prodotti vengono proposti almeno una volta.
    oggi_ordinale = datetime.date.today().toordinal()
    indice_partenza = (oggi_ordinale * k) % n

    scelti = []
    for i in range(k):
        scelti.append(prodotti[(indice_partenza + i) % n])
    return scelti


# ---------------------------------------------------------------------------
# STEP 3: GENERA DESCRIZIONI MANCANTI CON GEMINI (SE SERVE)
# ---------------------------------------------------------------------------

def genera_descrizione(nome_prodotto):
    from google import genai

    client = genai.Client()
    prompt = (
        f"Scrivi una singola frase breve (max 20 parole) in italiano che descriva in modo "
        f"accattivante questo prodotto per un pubblico di appassionati di metal detecting, "
        f"senza inventare specifiche tecniche che non conosci: '{nome_prodotto}'. "
        f"Rispondi SOLO con la frase, nient'altro."
    )
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return response.text.strip()


# ---------------------------------------------------------------------------
# STEP 4: GENERA IL MARKDOWN
# ---------------------------------------------------------------------------

def genera_markdown(prodotti_oggi):
    mesi_it = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
               "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    oggi = datetime.date.today()
    data_italiana = f"{oggi.day} {mesi_it[oggi.month - 1]} {oggi.year}"
    data_iso = oggi.isoformat()

    righe = [
        "---",
        f'title: "Prodotti consigliati — {data_italiana}"',
        f"date: {data_iso}",
        "draft: false",
        'tags: ["offerte", "prodotti"]',
        'categories: ["offerte"]',
        "---",
        "",
        "*Link di affiliazione Amazon: se acquisti tramite questi link, "
        "riceviamo una piccola commissione senza costi aggiuntivi per te.*",
        "",
    ]

    for p in prodotti_oggi:
        descrizione = p["descrizione"]
        if not descrizione:
            print(f"  Genero descrizione per: {p['nome']}...")
            try:
                descrizione = genera_descrizione(p["nome"])
            except Exception as e:
                print(f"  Attenzione: impossibile generare descrizione ({e})")
                descrizione = ""

        righe.append(f"### {p['nome']}")
        if descrizione:
            righe.append(descrizione)
        righe.append("")
        righe.append(f"[Vedi su Amazon]({p['link']})")
        righe.append("")

    return "\n".join(righe)


# ---------------------------------------------------------------------------
# STEP 5: SALVATAGGIO
# ---------------------------------------------------------------------------

def salva(contenuto):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    oggi = datetime.date.today().isoformat()
    percorso = os.path.join(OUTPUT_DIR, f"offerte-{oggi}.md")
    with open(percorso, "w", encoding="utf-8") as f:
        f.write(contenuto)
    print(f"\nPost offerte salvato in: {percorso}")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    prodotti = leggi_prodotti()
    print(f"Prodotti in libreria: {len(prodotti)}")

    scelti = scegli_prodotti_oggi(prodotti)
    print(f"Prodotti scelti per oggi: {', '.join(p['nome'] for p in scelti)}\n")

    markdown = genera_markdown(scelti)
    salva(markdown)


if __name__ == "__main__":
    main()
