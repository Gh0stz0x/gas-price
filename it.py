#!/usr/bin/python3
# -*- coding: utf-8 -*-

import click
import sys
import requests
import os.path
import io
import csv
import writer
import html

# Utility to clean filenames (replaces spaces and slashes)
def clean_filename(name):
    return "".join([c if c.isalnum() else "_" for c in name]).lower()

def get_clean_reader(content_lines):
    """Detects header and delimiter (| or ;) and returns a DictReader."""
    start_index = 0
    delim = ';'
    for i, line in enumerate(content_lines[:10]):
        if "idImpianto" in line:
            start_index = i
            delim = '|' if '|' in line else ';'
            break
    return csv.DictReader(content_lines[start_index:], delimiter=delim)

def parse_mimit(price_reader, impianti, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    # Dictionary to keep track of active KML writers
    # key: fuel name, value: KmlWriter object
    active_writers = {}

    processed = 0
    print("Starting KML generation by fuel type...")

    for row in price_reader:
        id_imp = row.get('idImpianto')
        if id_imp in impianti:
            info = impianti[id_imp]
            fuel_raw = row.get('descCarburante', 'Unknown').strip()
            price = row.get('prezzo', '0')
            is_self = "Self" if row.get('isSelf') == '1' else "Servito"

            # 1. CLEAN COORDINATES (Fixes "ref position" error)
            try:
                lat_str = str(info['lat']).replace(',', '.')
                lon_str = str(info['lon']).replace(',', '.')
                lat, lon = float(lat_str), float(lon_str)
                if lat == 0 or lon == 0: continue
            except: continue

            # 2. DATE CONVERSION
            raw_date = row.get('dtComu', '')
            try:
                d_p, t_p = raw_date.split(' ')
                d, m, y = d_p.split('/')
                dt_iso = f"{y}-{m}-{d}T{t_p}Z"
            except: dt_iso = ""

            # 3. DYNAMIC WRITER SELECTION
            # If we haven't seen this fuel type yet, create a new KML file for it
            if fuel_raw not in active_writers:
                fname = f"{clean_filename(fuel_raw)}.kml"
                # Assign a color based on some keywords
                color = "yellow" # Default (Diesel)
                if "benzina" in fuel_raw.lower(): color = "green"
                elif "gpl" in fuel_raw.lower(): color = "blue"
                elif "metano" in fuel_raw.lower() or "gnl" in fuel_raw.lower(): color = "white"
                elif "blue" in fuel_raw.lower() or "special" in fuel_raw.lower(): color = "cyan"

                active_writers[fuel_raw] = writer.KmlWriter(
                    os.path.join(out_dir, fname),
                    f"Italy - {fuel_raw}",
                    "Mimit",
                    color
                )

            w = active_writers[fuel_raw]

            # 4. WRITE DATA
            brand = html.escape(info.get('brand', 'Unknown'))
            label = html.escape(f"{price} - {fuel_raw} ({brand})")
            w.writeStation(label, dt_iso, lon, lat, is_self)
            processed += 1

    # Close all opened KML files
    for w in active_writers.values():
        w.close()

    print(f"Extraction complete! Created {len(active_writers)} separate KML files.")
    print(f"Total records processed: {processed}")

@click.command()
@click.option("-i", "file_in", help="Local price CSV file (e.g. prezzo_alle_8.csv)")
@click.option("-o", "out", default=".", help="Output directory")

def main(file_in, out):
    URL_ANAGRAFICA = "https://www.mimit.gov.it/images/exportCSV/anagrafica_impianti_attivi.csv"
    URL_PREZZI = "https://www.mimit.gov.it/images/exportCSV/prezzo_alle_8.csv"

    # 1. Load Metadata
    print("Fetching station metadata...")
    try:
        r = requests.get(URL_ANAGRAFICA, timeout=20)
        lines = r.content.decode('latin-1', errors='ignore').splitlines()
        reader = get_clean_reader(lines)
        impianti = {row['idImpianto']: {
            'lat': row.get('Latitudine'),
            'lon': row.get('Longitudine'),
            'brand': row.get('Bandiera', 'Unknown')
        } for row in reader if row.get('idImpianto')}
    except Exception as e:
        print(f"Error loading metadata: {e}")
        return

    # 2. Process Prices
    if file_in:
        print(f"Reading local file: {file_in}")
        with open(file_in, 'r', encoding='utf-8', errors='ignore') as f:
            price_reader = get_clean_reader(f.readlines())
            parse_mimit(price_reader, impianti, out)
    else:
        print("Downloading online prices...")
        r = requests.get(URL_PREZZI, timeout=20)
        lines = r.content.decode('latin-1', errors='ignore').splitlines()
        price_reader = get_clean_reader(lines)
        parse_mimit(price_reader, impianti, out)

if __name__ == '__main__':
    main()
