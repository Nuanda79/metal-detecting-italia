#!/usr/bin/env python3
"""
News Aggregator per Metal Detecting Italia.

Legge una lista di feed RSS, prende gli articoli delle ultime N ore,
li passa a Gemini (livello gratuito) per un riassunto/verifica in italiano
(rispettando il copyright: parafrasi, mai copia integrale), e genera un
file Markdown pronto per Hugo in content/news/.

Uso:
    export GEMINI_API_KEY="la-tua-chiave"
    python news_aggregator.py
"""

import os
import sys
import time
import datetime
import feedparser
from google import genai

# ---------------------------------------------------------------------------
# CONFIGURAZIONE
# ---------------------------------------------------------------------------

# Elenco dei feed RSS da monitorare: (nome_fonte, url_feed, tipo)
# tipo "news"  = il feed contiene un estratto/contenuto reale dell'articolo -> riassunto narrativo
# tipo "forum" = il feed contiene solo titolo+autore+link (niente testo reale) -> solo link pulito, mai inventare contenuto
FEEDS = [
    ("AMDTT", "http://www.amdtt.it/feed/", "news"),
    ("Smart Metal Detecting Forum Italia",
     "https://smartmetaldetecting.forumfree.it/rss.php?c=1053727", "forum"),
    ("Metal Detector Italia",
     "https://metaldetectoritalia.forumfree.it/rss.php?c=785967", "forum"),
    ("Google Alerts - metal detecting Italia",
     "https://www.google.com/alerts/feeds/05822292333570060675/13048064364440278890", "news"),
    ("Google Alerts - ritrovamento archeologico metal detector",
     "https://www.google.com/alerts/feeds/05822292333570060675/2019173468446488211", "news"),
    ("Google Alerts - nuovo metal detector 2026",
     "https://www.google.com/alerts/feeds/05822292333570060675/16821163139513406232", "news"),
]

# Quante ore indietro guardare (24-48h consigliato per un digest giornaliero)
FINESTRA_ORE = 36

# Percorso di output: la cartella content/news/ del sito Hugo
# Modifica questo path per farlo puntare alla cartella del tuo sito
OUTPUT_DIR = "content/news"

# Modello Gemini da usare (Flash è gratuito nei limiti del livello free, ottimo per riassumere)
MODEL = "gemini-2.5-flash"


# ---------------------------------------------------------------------------
# STEP 1: RACCOLTA ARTICOLI DAI FEED RSS
# ---------------------------------------------------------------------------

def raccogli_articoli():
    """Scarica tutti i feed e restituisce gli articoli recenti."""
    ora_limite = datetime.datetime.now() - datetime.timedelta(hours=FINESTRA_ORE)
    articoli = []

    for nome_fonte, url, tipo in FEEDS:
        print(f"Leggo feed: {nome_fonte}...")
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"  Errore nel leggere {nome_fonte}: {e}")
            continue

        if feed.bozo and not feed.entries:
            print(f"  ATTENZIONE: feed non valido o vuoto per {nome_fonte}")
            continue

        for entry in feed.entries:
            # Prova a determinare la data di pubblicazione
            data_pub = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                data_pub = datetime.datetime.fromtimestamp(
                    time.mktime(entry.published_parsed)
                )
            elif hasattr(entry, "updated_parsed") and entry.updated_parsed:
                data_pub = datetime.datetime.fromtimestamp(
                    time.mktime(entry.updated_parsed)
                )

            # Se non c'è data, includiamo comunque l'articolo (meglio includere
            # che perdere una notizia - la deduplica successiva pulirà eventuali doppioni)
            if data_pub is not None and data_pub < ora_limite:
                continue

            titolo = getattr(entry, "title", "Senza titolo")
            link = getattr(entry, "link", "")
            estratto = getattr(entry, "summary", "")

            # I forum ForumFree includono nel feed anche link a intere sezioni/board
            # (pattern "?f=...") oltre alle vere discussioni (pattern "?t=...").
            # Le sezioni non sono "notizie del giorno", sono link statici: le scartiamo.
            if tipo == "forum":
                if "?t=" not in link:
                    continue
                # Per i forum richiediamo anche una data valida e recente: senza data
                # non possiamo sapere se è un post di oggi o di 3 anni fa.
                if data_pub is None or data_pub < ora_limite:
                    continue
                # Il campo summary contiene solo markup (autore + link), non un vero
                # estratto: lo azzeriamo per evitare che il modello lo scambi per
                # materiale su cui scrivere un riassunto narrativo.
                estratto = ""

            articoli.append({
                "fonte": nome_fonte,
                "tipo": tipo,
                "titolo": titolo,
                "link": link,
                "estratto": estratto[:500],  # limitiamo la lunghezza
                "data": data_pub.isoformat() if data_pub else None,
            })

        print(f"  Trovati {len(feed.entries)} articoli totali nel feed.")

    print(f"\nTotale articoli recenti raccolti: {len(articoli)}")
    return articoli


# ---------------------------------------------------------------------------
# STEP 2: RIASSUNTO E VERIFICA CON CLAUDE
# ---------------------------------------------------------------------------

def genera_digest(articoli):
    """Passa gli articoli a Claude per riassumerli in un digest markdown."""
    if not articoli:
        return None

    client = genai.Client()  # legge automaticamente GEMINI_API_KEY dall'ambiente

    # Calcoliamo la data ODIERNA REALE qui in Python (mai lasciarla indovinare al modello)
    mesi_it = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
               "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    oggi = datetime.date.today()
    data_italiana = f"{oggi.day} {mesi_it[oggi.month - 1]} {oggi.year}"
    data_iso = oggi.isoformat()

    # Separiamo gli articoli in due gruppi: quelli con contenuto reale (news)
    # e quelli che sono solo titolo+link di discussioni forum (niente testo reale)
    articoli_news = [a for a in articoli if a["tipo"] == "news"]
    articoli_forum = [a for a in articoli if a["tipo"] == "forum"]

    materiale_news = "\n\n".join(
        f"FONTE: {a['fonte']}\nTITOLO: {a['titolo']}\nLINK: {a['link']}\nESTRATTO: {a['estratto']}"
        for a in articoli_news
    ) or "(nessuna notizia con contenuto reale oggi)"

    materiale_forum = "\n".join(
        f"- TITOLO: {a['titolo']} | FONTE: {a['fonte']} | LINK: {a['link']}"
        for a in articoli_forum
    ) or "(nessuna discussione forum oggi)"

    prompt = f"""Sei l'editor di un sito italiano dedicato al metal detecting.
Ti fornisco due gruppi di materiale grezzo raccolti da feed RSS.

GRUPPO 1 - NOTIZIE CON CONTENUTO REALE (blog, alert Google):
Per ognuna, se rilevante per il metal detecting, scrivi 2-3 frasi di riassunto
IN ITALIANO, PARAFRASANDO con parole tue (mai copiare frasi originali), citando
la fonte con un link markdown. Scarta solo se chiaramente irrilevante o spam
(es. articoli che citano "metal detector" in un contesto non attinente, come
controlli di sicurezza a eventi/concerti).

GRUPPO 2 - DISCUSSIONI FORUM (solo titolo, NESSUN contenuto reale disponibile):
Per questi NON hai il contenuto del post, solo il titolo della discussione.
NON INVENTARE MAI un riassunto o una descrizione di cosa dice la discussione:
sarebbe informazione falsa. Limitati a presentarle come un elenco puntato con
il titolo esatto della discussione e il link, senza aggiungere alcuna frase
esplicativa o interpretativa.

Organizza il risultato in un file Markdown con ESATTAMENTE questo formato,
usando la data che ti fornisco qui sotto (non inventarla, non cambiarla):

---
title: "Rassegna del giorno — {data_italiana}"
date: {data_iso}
draft: false
tags: ["news", "rassegna"]
categories: ["news"]
---

## Notizie del giorno

[qui i riassunti narrativi del GRUPPO 1, ognuno con ### Titolo riformulato seguito
dal riassunto e dal link fonte - ometti questa sezione se il gruppo 1 è vuoto]

## Dai forum

[qui l'elenco puntato del GRUPPO 2, formato: "- [Titolo esatto della discussione](link) — FonteForum"
- ometti questa sezione se il gruppo 2 è vuoto]

Se DAVVERO entrambi i gruppi sono vuoti o irrilevanti, scrivi comunque il
frontmatter sopra e poi la riga "Nessuna novità rilevante raccolta oggi."
Ma prima controlla con attenzione: preferisci includere un contenuto dubbio
del GRUPPO 1 piuttosto che scartarlo senza motivo (per il GRUPPO 2 invece
includi sempre tutte le discussioni, non ci sono rischi di inventare nulla
dato che sono solo link).

Rispondi SOLO con il contenuto del file Markdown, nient'altro (niente premesse, niente
markdown fence \\`\\`\\`).

GRUPPO 1 - NOTIZIE:
{materiale_news}

GRUPPO 2 - DISCUSSIONI FORUM:
{materiale_forum}
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
    )

    return response.text.strip()


# ---------------------------------------------------------------------------
# STEP 3: SALVATAGGIO DEL FILE MARKDOWN
# ---------------------------------------------------------------------------

def salva_digest(contenuto):
    """Salva il digest come file markdown nella cartella content/news/ di Hugo."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    oggi = datetime.date.today().isoformat()
    nome_file = f"rassegna-{oggi}.md"
    percorso = os.path.join(OUTPUT_DIR, nome_file)

    with open(percorso, "w", encoding="utf-8") as f:
        f.write(contenuto)

    print(f"\nDigest salvato in: {percorso}")
    return percorso


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    if "GEMINI_API_KEY" not in os.environ:
        print("ERRORE: variabile d'ambiente GEMINI_API_KEY non impostata.")
        print('Esegui prima: export GEMINI_API_KEY="la-tua-chiave"')
        sys.exit(1)

    articoli = raccogli_articoli()

    if not articoli:
        print("Nessun articolo recente trovato. Nessun digest generato.")
        sys.exit(0)

    print("\nGenero il digest con Gemini...")
    digest = genera_digest(articoli)

    if not digest:
        print("Errore: digest vuoto.")
        sys.exit(1)

    if "nessuna novità rilevante" in digest.lower():
        print("\nNessuna notizia rilevante oggi: non pubblico un post vuoto.")
        sys.exit(0)

    salva_digest(digest)


if __name__ == "__main__":
    main()
