#!/usr/bin/python3
# -*- coding: utf-8 -*-

import click
import requests
import os
import os.path
import csv
import writer
import html

# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def clean_filename(name):
    """Pulisce il nome per usarlo come filename."""
    return "".join([c if c.isalnum() else "_" for c in name]).lower()

def get_clean_reader(content_lines):
    """Rileva header e delimitatore (| o ;) e restituisce un DictReader."""
    start_index = 0
    delim = ';'
    for i, line in enumerate(content_lines[:10]):
        if "idImpianto" in line:
            start_index = i
            delim = '|' if '|' in line else ';'
            break
    return csv.DictReader(content_lines[start_index:], delimiter=delim)

def get_fuel_color(fuel_raw):
    """Assegna un colore in base al tipo di carburante (usato solo per KML)."""
    fuel_lower = fuel_raw.lower()
    if "benzina" in fuel_lower:                           return "green"
    elif "gpl" in fuel_lower:                             return "blue"
    elif "metano" in fuel_lower or "gnl" in fuel_lower:   return "white"
    elif "blue" in fuel_lower or "special" in fuel_lower: return "cyan"
    elif "hvo" in fuel_lower:                             return "orange"
    elif "idrogeno" in fuel_lower:                        return "purple"
    elif "elettr" in fuel_lower:                          return "red"
    else:                                                 return "yellow"

def is_valid_price(price_str):
    """Restituisce True se il prezzo è plausibile (0.01 – 5.00 €)."""
    try:
        p = float(price_str.replace(',', '.'))
        return 0.01 <= p <= 5.00
    except (ValueError, TypeError):
        return False

# ---------------------------------------------------------------------------
# Core parsing
# ---------------------------------------------------------------------------

def parse_mimit_kml(price_reader, impianti, out_dir):
    """Genera un file KML per ogni tipo di carburante (comportamento originale)."""
    os.makedirs(out_dir, exist_ok=True)
    active_writers = {}
    processed = 0
    skipped = 0

    print("Modalità KML — un file per tipo di carburante...")

    for row in price_reader:
        id_imp = row.get('idImpianto')
        if id_imp not in impianti:
            continue

        info     = impianti[id_imp]
        fuel_raw = row.get('descCarburante', 'Unknown').strip()
        price    = row.get('prezzo', '0')
        is_self  = "Self" if row.get('isSelf') == '1' else "Servito"

        # Coordinate
        try:
            lat = float(str(info['lat']).replace(',', '.'))
            lon = float(str(info['lon']).replace(',', '.'))
            if lat == 0 or lon == 0:
                skipped += 1
                continue
        except (ValueError, TypeError):
            skipped += 1
            continue

        # Prezzo
        if not is_valid_price(price):
            skipped += 1
            continue

        # Data
        raw_date = row.get('dtComu', '')
        try:
            d_p, t_p = raw_date.split(' ')
            d, m, y  = d_p.split('/')
            dt_iso   = f"{y}-{m}-{d}T{t_p}Z"
        except (ValueError, AttributeError):
            dt_iso = ""

        # Writer KML
        if fuel_raw not in active_writers:
            fname = f"{clean_filename(fuel_raw)}.kml"
            color = get_fuel_color(fuel_raw)
            active_writers[fuel_raw] = writer.KmlWriter(
                os.path.join(out_dir, fname),
                f"Italy - {fuel_raw}",
                "Mimit",
                color
            )

        brand = html.escape(info.get('brand', 'Unknown'))
        label = html.escape(f"{price} - {fuel_raw} ({brand})")
        active_writers[fuel_raw].writeStation(label, dt_iso, lon, lat, is_self)
        processed += 1

    for w in active_writers.values():
        w.close()

    print(f"Completato! Creati {len(active_writers)} file KML.")
    print(f"Record elaborati: {processed}  |  Saltati: {skipped}")


def parse_mimit_gpx(price_reader, impianti, out_dir):
    """Genera un singolo file GPX con gruppi OsmAnd per tipo di carburante."""
    os.makedirs(out_dir, exist_ok=True)
    processed = 0
    skipped = 0

    print("Modalità GPX — file unico con gruppi OsmAnd...")

    gpx_path = os.path.join(out_dir, "italy_carburanti.gpx")
    gpx = writer.GpxWriter(gpx_path, "Italy - Carburanti", "Mimit")

    for row in price_reader:
        id_imp = row.get('idImpianto')
        if id_imp not in impianti:
            continue

        info     = impianti[id_imp]
        fuel_raw = row.get('descCarburante', 'Unknown').strip()
        price    = row.get('prezzo', '0')
        is_self  = "Self" if row.get('isSelf') == '1' else "Servito"

        # Coordinate
        try:
            lat = float(str(info['lat']).replace(',', '.'))
            lon = float(str(info['lon']).replace(',', '.'))
            if lat == 0 or lon == 0:
                skipped += 1
                continue
        except (ValueError, TypeError):
            skipped += 1
            continue

        # Prezzo
        if not is_valid_price(price):
            skipped += 1
            continue

        # Data
        raw_date = row.get('dtComu', '')
        try:
            d_p, t_p = raw_date.split(' ')
            d, m, y  = d_p.split('/')
            dt_iso   = f"{y}-{m}-{d}T{t_p}Z"
        except (ValueError, AttributeError):
            dt_iso = ""

        brand = html.escape(info.get('brand', 'Unknown'))
        label = html.escape(f"{price} - {fuel_raw} ({brand})")
        gpx.writeStation(label, dt_iso, lon, lat, is_self, fuel_raw)
        processed += 1

    gpx.close()

    print(f"Completato! File GPX: {gpx_path}")
    print(f"Record elaborati: {processed}  |  Saltati: {skipped}")


def parse_mimit_gpx_multi(price_reader, impianti, out_dir):
    """
    Genera un file GPX separato per ogni macro-categoria di carburante:
      - italy_benzina.gpx      (Benzina + Benzina Speciale)
      - italy_gasolio.gpx      (Gasolio + Gasolio Speciale)
      - italy_metano.gpx       (Metano / GNL)
      - italy_gpl.gpx          (GPL)
      - italy_hvo.gpx          (HVO)
      - italy_idrogeno.gpx     (Idrogeno)
      - italy_elettrico.gpx    (Elettrico)
      - italy_altro.gpx        (non classificato)
    """
    os.makedirs(out_dir, exist_ok=True)
    processed = 0
    skipped = 0

    print("Modalità GPX Multi — un file per macro-categoria...")

    gpx_multi = writer.GpxMultiWriter(out_dir, "Mimit")

    for row in price_reader:
        id_imp = row.get('idImpianto')
        if id_imp not in impianti:
            continue

        info     = impianti[id_imp]
        fuel_raw = row.get('descCarburante', 'Unknown').strip()
        price    = row.get('prezzo', '0')
        is_self  = "Self" if row.get('isSelf') == '1' else "Servito"

        # Coordinate
        try:
            lat = float(str(info['lat']).replace(',', '.'))
            lon = float(str(info['lon']).replace(',', '.'))
            if lat == 0 or lon == 0:
                skipped += 1
                continue
        except (ValueError, TypeError):
            skipped += 1
            continue

        # Prezzo
        if not is_valid_price(price):
            skipped += 1
            continue

        # Data
        raw_date = row.get('dtComu', '')
        try:
            d_p, t_p = raw_date.split(' ')
            d, m, y  = d_p.split('/')
            dt_iso   = f"{y}-{m}-{d}T{t_p}Z"
        except (ValueError, AttributeError):
            dt_iso = ""

        brand = html.escape(info.get('brand', 'Unknown'))
        label = html.escape(f"{price} - {fuel_raw} ({brand})")
        gpx_multi.writeStation(label, dt_iso, lon, lat, is_self, fuel_raw)
        processed += 1

    files_written = gpx_multi.close()

    print(f"Completato! File GPX creati:")
    for fname, count in sorted(files_written, key=lambda x: -x[1]):
        print(f"  {fname}  ({count} waypoint)")
    print(f"Record elaborati: {processed}  |  Saltati: {skipped}")

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.command()
@click.option("-i", "file_in",  default=None, help="File CSV locale dei prezzi (es. prezzo_alle_8.csv)")
@click.option("-o", "out",      default=".",  help="Directory di output")
@click.option("-f", "fmt",      default=None,
              type=click.Choice(["kml", "gpx", "gpx-multi"], case_sensitive=False),
              help=(
                  "Formato di output:\n"
                  "  kml       → un file KML per tipo di carburante\n"
                  "  gpx       → un file GPX unico con gruppi OsmAnd\n"
                  "  gpx-multi → un file GPX per macro-categoria (benzina, gasolio, metano, gpl...)"
              ))
def main(file_in, out, fmt):

    # Se il formato non è stato passato da CLI, chiedi interattivamente
    if fmt is None:
        fmt = click.prompt(
            "Formato di output",
            type=click.Choice(["kml", "gpx", "gpx-multi"], case_sensitive=False),
            default="gpx-multi"
        )

    URL_ANAGRAFICA = "https://www.mimit.gov.it/images/exportCSV/anagrafica_impianti_attivi.csv"
    URL_PREZZI     = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"

    # 1. Carica anagrafica impianti
    print("Scarico anagrafica impianti...")
    try:
        r = requests.get(URL_ANAGRAFICA, timeout=20)
        lines = r.content.decode('latin-1', errors='ignore').splitlines()
        reader = get_clean_reader(lines)
        impianti = {
            row['idImpianto']: {
                'lat':   row.get('Latitudine'),
                'lon':   row.get('Longitudine'),
                'brand': row.get('Bandiera', 'Unknown')
            }
            for row in reader if row.get('idImpianto')
        }
        print(f"Impianti caricati: {len(impianti)}")
    except Exception as e:
        print(f"Errore nel caricamento anagrafica: {e}")
        return

    # 2. Scegli funzione di parsing
    fmt_lower = fmt.lower()
    if fmt_lower == "gpx-multi":
        parse_fn = parse_mimit_gpx_multi
    elif fmt_lower == "gpx":
        parse_fn = parse_mimit_gpx
    else:
        parse_fn = parse_mimit_kml

    # 3. Carica prezzi (locale o online)
    if file_in:
        print(f"Leggo file locale: {file_in}")
        try:
            with open(file_in, 'r', encoding='utf-8', errors='ignore') as f:
                price_reader = get_clean_reader(f.readlines())
                parse_fn(price_reader, impianti, out)
        except Exception as e:
            print(f"Errore nella lettura del file locale: {e}")
    else:
        print("Scarico prezzi online...")
        try:
            r = requests.get(URL_PREZZI, timeout=20)
            lines = r.content.decode('latin-1', errors='ignore').splitlines()
            price_reader = get_clean_reader(lines)
            parse_fn(price_reader, impianti, out)
        except Exception as e:
            print(f"Errore nel download prezzi: {e}")

if __name__ == '__main__':
    main()
