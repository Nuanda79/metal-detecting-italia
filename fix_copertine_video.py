#!/usr/bin/env python3
"""
Script una tantum: aggiunge 'hiddenInSingle: true' sotto il blocco cover
di tutti i file video già esistenti in content/video/, per nascondere la
copertina ridondante nella pagina del singolo video (fix retroattivo).

Uso (lanciare UNA VOLTA dalla cartella del sito, es. metal-detecting-italia):
    python fix_copertine_video.py
"""

import os
import glob

CARTELLA = "content/video"


def main():
    if not os.path.isdir(CARTELLA):
        print(f"ERRORE: cartella '{CARTELLA}' non trovata. Lancia lo script "
              f"dalla cartella principale del sito (metal-detecting-italia).")
        return

    file_trovati = glob.glob(os.path.join(CARTELLA, "*.md"))
    aggiornati = 0
    saltati_gia_ok = 0
    saltati_senza_cover = 0

    for path in file_trovati:
        if os.path.basename(path) == "_index.md":
            continue

        with open(path, "r", encoding="utf-8") as f:
            contenuto = f.read()

        if "hiddenInSingle" in contenuto:
            saltati_gia_ok += 1
            continue

        if "cover:" not in contenuto:
            saltati_senza_cover += 1
            continue

        righe = contenuto.split("\n")
        nuove_righe = []
        for riga in righe:
            nuove_righe.append(riga)
            if riga.strip().startswith("alt:"):
                indent = riga[:len(riga) - len(riga.lstrip())]
                nuove_righe.append(f"{indent}hiddenInSingle: true")

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(nuove_righe))

        print(f"Aggiornato: {path}")
        aggiornati += 1

    print(f"\nFatto. Aggiornati: {aggiornati}, "
          f"già a posto: {saltati_gia_ok}, senza copertina: {saltati_senza_cover}")


if __name__ == "__main__":
    main()
