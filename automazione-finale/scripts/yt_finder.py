#!/usr/bin/env python3
"""
YouTube Video Finder per Metal Detecting Italia.

Controlla i canali YouTube configurati, trova i video pubblicati nelle
ultime N ore, e genera un file Markdown con gli embed pronti per Hugo.

Uso:
    export YOUTUBE_API_KEY="la-tua-chiave"
    python yt_finder.py
"""

import os
import sys
import datetime
import requests

# ---------------------------------------------------------------------------
# CONFIGURAZIONE
# ---------------------------------------------------------------------------

# Elenco canali: (nome_visualizzato, handle_con_@ OPPURE ID_canale diretto)
# Per aggiungerne uno nuovo in futuro basta aggiungere una riga qui.
CHANNELS = [
    ("DetectorShop Italia", "UC5Sp7Gb6nKtU8jY4RB8AqSQ"),
    ("Daniel Facose", "@DanielFaCoseInVan"),
    ("XP Metal Detectors", "@xpmetaldetector"),
    ("Nuanda1979", "@Nuanda1979"),
    ("Detector Center", "UC8fejpBB1om6VjC4GRnPEsw"),
    ("L'ultimo Recuperante", "@lultimorecuperante"),
    ("RRS MetalDetector Fede&Anto", "@RRSMetalDetector"),
    ("The Hoover Boys", "@thehooverboys"),
]

# Quante ore indietro guardare
FINESTRA_ORE = 48

# Percorso di output: la cartella content/video/ del sito Hugo
OUTPUT_DIR = "content/video"

API_BASE = "https://www.googleapis.com/youtube/v3"


# ---------------------------------------------------------------------------
# STEP 1: RISOLVI OGNI CANALE NELLA SUA PLAYLIST "UPLOADS"
# ---------------------------------------------------------------------------

def risolvi_uploads_playlist(api_key, identificativo):
    """Dato un handle (@nome) o un ID canale (UC...), restituisce l'ID
    della playlist 'uploads' del canale (contiene tutti i video in ordine
    cronologico, è il modo più economico in quota per leggerli)."""
    if identificativo.startswith("@"):
        params = {"part": "contentDetails", "forHandle": identificativo[1:], "key": api_key}
    else:
        params = {"part": "contentDetails", "id": identificativo, "key": api_key}

    r = requests.get(f"{API_BASE}/channels", params=params, timeout=15)
    r.raise_for_status()
    items = r.json().get("items", [])
    if not items:
        return None
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


# ---------------------------------------------------------------------------
# STEP 2: PRENDI I VIDEO RECENTI DALLA PLAYLIST UPLOADS
# ---------------------------------------------------------------------------

def video_recenti(api_key, playlist_id, ora_limite_utc):
    """Restituisce i video della playlist pubblicati dopo ora_limite_utc."""
    params = {
        "part": "snippet",
        "playlistId": playlist_id,
        "maxResults": 10,
        "key": api_key,
    }
    r = requests.get(f"{API_BASE}/playlistItems", params=params, timeout=15)
    r.raise_for_status()

    risultati = []
    for item in r.json().get("items", []):
        snippet = item["snippet"]
        pub_str = snippet.get("publishedAt")  # es. 2026-07-14T09:00:00Z
        if not pub_str:
            continue
        pub_dt = datetime.datetime.fromisoformat(pub_str.replace("Z", "+00:00"))

        if pub_dt < ora_limite_utc:
            continue

        risorsa = snippet.get("resourceId", {})
        video_id = risorsa.get("videoId")
        if not video_id:
            continue

        risultati.append({
            "titolo": snippet.get("title", "Senza titolo"),
            "video_id": video_id,
            "data": pub_dt,
        })

    return risultati


# ---------------------------------------------------------------------------
# STEP 3: RACCOLTA COMPLETA SU TUTTI I CANALI
# ---------------------------------------------------------------------------

def raccogli_video(api_key):
    ora_limite = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=FINESTRA_ORE)
    tutti_i_video = []

    for nome_canale, identificativo in CHANNELS:
        print(f"Controllo canale: {nome_canale}...")
        try:
            playlist_id = risolvi_uploads_playlist(api_key, identificativo)
        except requests.HTTPError as e:
            print(f"  Errore nel risolvere il canale: {e}")
            continue

        if not playlist_id:
            print(f"  ATTENZIONE: canale non trovato per '{identificativo}'")
            continue

        try:
            video = video_recenti(api_key, playlist_id, ora_limite)
        except requests.HTTPError as e:
            print(f"  Errore nel leggere i video: {e}")
            continue

        for v in video:
            v["canale"] = nome_canale
            tutti_i_video.append(v)

        print(f"  Trovati {len(video)} video recenti.")

    # Ordiniamo dal più recente
    tutti_i_video.sort(key=lambda v: v["data"], reverse=True)

    print(f"\nTotale video recenti raccolti: {len(tutti_i_video)}")
    return tutti_i_video


# ---------------------------------------------------------------------------
# STEP 4: GENERA IL MARKDOWN CON GLI EMBED
# ---------------------------------------------------------------------------

def genera_markdown(video):
    mesi_it = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
               "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]
    oggi = datetime.date.today()
    data_italiana = f"{oggi.day} {mesi_it[oggi.month - 1]} {oggi.year}"
    data_iso = oggi.isoformat()

    righe = [
        "---",
        f'title: "Video del giorno — {data_italiana}"',
        f"date: {data_iso}",
        "draft: false",
        'tags: ["video", "youtube"]',
        'categories: ["video"]',
        "---",
        "",
    ]

    if not video:
        righe.append("Nessun nuovo video oggi dai canali monitorati.")
        return "\n".join(righe)

    for v in video:
        righe.append(f"### {v['titolo']}")
        righe.append(f"*Canale: {v['canale']}*")
        righe.append("")
        righe.append(f"{{{{< youtube {v['video_id']} >}}}}")
        righe.append("")

    return "\n".join(righe)


# ---------------------------------------------------------------------------
# STEP 5: SALVATAGGIO
# ---------------------------------------------------------------------------

def salva(contenuto):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    oggi = datetime.date.today().isoformat()
    percorso = os.path.join(OUTPUT_DIR, f"video-{oggi}.md")
    with open(percorso, "w", encoding="utf-8") as f:
        f.write(contenuto)
    print(f"\nPost video salvato in: {percorso}")
    return percorso


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("ERRORE: variabile d'ambiente YOUTUBE_API_KEY non impostata.")
        print('Esegui prima: $env:YOUTUBE_API_KEY="la-tua-chiave"  (PowerShell)')
        sys.exit(1)

    video = raccogli_video(api_key)

    if not video:
        print("\nNessun video nuovo: non pubblico un post vuoto.")
        sys.exit(0)

    markdown = genera_markdown(video)
    salva(markdown)


if __name__ == "__main__":
    main()
