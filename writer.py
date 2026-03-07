# SPDX-FileCopyrightText: 2024 Cédric Bosdonnat <cedric.bosdonnat@gmail.com>
#
# SPDX-License-Identifier: MIT

# -*- coding: utf-8 -*-

import os
from datetime import datetime


# Mappa colori → codice HEX per il GPX OsmAnd
COLOR_HEX = {
    "green":  "#00AA00",
    "yellow": "#CCAA00",
    "blue":   "#0055FF",
    "white":  "#CCCCCC",
    "cyan":   "#00CCCC",
    "orange": "#FF8800",
    "purple": "#8800CC",
    "red":    "#CC0000",
}


class KmlWriter:
    """
    Write a gas prices KML file for Organic Maps / OsmAnd.
    """

    def __init__(self, filepath, name, source, color):
        self.filepath = filepath
        self._fd = open(filepath, "w", encoding="utf-8")
        self.name = name
        self.color = color

        now = datetime.now().isoformat(' ', timespec='minutes')
        self._fd.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://earth.google.com/kml/2.2">
<Document>
  <Style id="placemark-{color}">
    <IconStyle>
      <Icon>
        <href>https://omaps.app/placemarks/placemark-{color}.png</href>
      </Icon>
    </IconStyle>
  </Style>
  <name>{name}</name>
  <visibility>1</visibility>
  <ExtendedData xmlns:mwm="https://omaps.app">
    <mwm:name>
      <mwm:lang code="default">{name}</mwm:lang>
    </mwm:name>
    <mwm:annotation>
    </mwm:annotation>
    <mwm:description>
      <mwm:lang code="en">Generated from {source} data on {now}</mwm:lang>
      <mwm:lang code="fr">Généré à partir des données de {source} à {now}</mwm:lang>
      <mwm:lang code="it">Generato dai dati {source} il {now}</mwm:lang>
      <mwm:lang code="es">Generado a partir de los datos de {source} el {now}</mwm:lang>
    </mwm:description>
    <mwm:accessRules>Local</mwm:accessRules>
  </ExtendedData>
""")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self):
        if not self._fd.closed:
            self._fd.write("""</Document>
</kml>""")
            self._fd.close()

    def writeStation(self, price, update_time, lon, lat, vending):
        self._fd.write(f"""  <Placemark>
    <name>{price}</name>
    <TimeStamp><when>{update_time}</when></TimeStamp>
    <styleUrl>#placemark-{self.color}</styleUrl>
    <Point><coordinates>{lon},{lat}</coordinates></Point>
    <ExtendedData xmlns:mwm="https://omaps.app">
      <mwm:name><mwm:lang code="default">{price}</mwm:lang></mwm:name>
      <mwm:description>
        <mwm:lang code="default">Automate: {vending}</mwm:lang>
        <mwm:lang code="it">Modalità: {vending}</mwm:lang>
        <mwm:lang code="es">Modo: {vending}</mwm:lang>
      </mwm:description>
      <mwm:icon>Gas</mwm:icon>
    </ExtendedData>
  </Placemark>
""")


class GpxWriter:
    """
    Write a gas prices GPX file with OsmAnd waypoint groups.
    Un singolo file con tutti i carburanti raggruppati per categoria.
    """

    # Definizione dei gruppi: nome categoria → (colore hex, icona OsmAnd)
    GROUPS = {
        "Benzina":          (COLOR_HEX["green"],  "fuel"),
        "Benzina Speciale": (COLOR_HEX["cyan"],   "fuel"),
        "Gasolio":          (COLOR_HEX["yellow"], "fuel"),
        "Gasolio Speciale": (COLOR_HEX["orange"], "fuel"),
        "GPL":              (COLOR_HEX["blue"],   "fuel"),
        "Metano / GNL":     (COLOR_HEX["white"],  "fuel"),
        "HVO":              (COLOR_HEX["purple"], "fuel"),
        "Idrogeno":         (COLOR_HEX["purple"], "fuel"),
        "Elettrico":        (COLOR_HEX["red"],    "fuel"),
        "Altro":            (COLOR_HEX["yellow"], "fuel"),
    }

    # Mappa di normalizzazione: parole chiave → categoria
    FUEL_MAP = [
        # Benzina speciale (prima di benzina generica)
        (["v-power",  "excellium 9", "supreme ben", "especial ben",
          "ultimate", "momentum", "evo ben", "racing"], "Benzina Speciale"),
        # Benzina generica
        (["benzina", "super sp", "super 95", "super 98", "gasolio senza", "sp95", "sp98"], "Benzina"),
        # Gasolio speciale (prima di gasolio generico)
        (["v-power d", "excellium d", "supreme d", "blue diesel", "iq diesel",
          "energy diesel", "excelium d", "oro", "premium", "prestazional",
          "speciale", "artic", "alpin", "invernale", "hvo diesel"], "Gasolio Speciale"),
        # Gasolio generico
        (["gasolio", "diesel", "blu", "gasol"], "Gasolio"),
        # GPL
        (["gpl", "autogas", "lpg"], "GPL"),
        # Metano / GNL
        (["metano", "gnl", "gnc", "cng", "lng"], "Metano / GNL"),
        # HVO
        (["hvo"], "HVO"),
        # Idrogeno
        (["idrogeno", "hydrogen", "h2"], "Idrogeno"),
        # Elettrico
        (["elettr", "electric", "ev ", "ricaric"], "Elettrico"),
    ]

    def __init__(self, filepath, name, source):
        self.filepath = filepath
        self._fd = open(filepath, "w", encoding="utf-8")
        self.name = name
        self.source = source
        self._waypoints = []   # lista di tuple (lat, lon, label, category, vending, dt_iso)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    @staticmethod
    def normalize_fuel(fuel_raw):
        """Normalizza il nome grezzo del carburante in una categoria standard."""
        fuel_lower = fuel_raw.lower()
        for keywords, category in GpxWriter.FUEL_MAP:
            if any(kw in fuel_lower for kw in keywords):
                return category
        return "Altro"

    def writeStation(self, label, dt_iso, lon, lat, vending, fuel_raw):
        """Accumula il waypoint in memoria (scrittura avviene al close)."""
        category = self.normalize_fuel(fuel_raw)
        self._waypoints.append((lat, lon, label, category, vending, dt_iso))

    def close(self):
        """Scrive il file GPX completo con tutti i waypoint e i gruppi OsmAnd."""
        if self._fd.closed:
            return

        now = datetime.now().isoformat(' ', timespec='minutes')

        # Raccoglie solo i gruppi effettivamente usati
        used_groups = {wp[3] for wp in self._waypoints}

        self._fd.write(f"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.1" creator="pododoo"
     xmlns="http://www.topografix.com/GPX/1/1"
     xmlns:osmand="https://osmand.net"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://www.topografix.com/GPX/1/1
       http://www.topografix.com/GPX/1/1/gpx.xsd">
  <metadata>
    <name>{self.name}</name>
    <desc>Generated from {self.source} data on {now}</desc>
  </metadata>
""")

        # Waypoints
        for lat, lon, label, category, vending, dt_iso in self._waypoints:
            color_hex = self.GROUPS.get(category, (COLOR_HEX["yellow"], "fuel"))[0]
            time_tag = f"\n    <time>{dt_iso}</time>" if dt_iso else ""
            self._fd.write(f"""  <wpt lat="{lat}" lon="{lon}">
    <name>{label}</name>{time_tag}
    <type>{category}</type>
    <desc>Modalità: {vending} / Modo: {vending}</desc>
    <extensions>
      <osmand:color>{color_hex}</osmand:color>
      <osmand:icon>fuel</osmand:icon>
      <osmand:background>circle</osmand:background>
    </extensions>
  </wpt>
""")

        # Definizione gruppi OsmAnd (solo quelli usati)
        self._fd.write("  <extensions>\n    <osmand:points_groups>\n")
        for group_name, (color_hex, icon) in self.GROUPS.items():
            if group_name in used_groups:
                self._fd.write(
                    f'      <group name="{group_name}" color="{color_hex}" '
                    f'icon="{icon}" background="circle"/>\n'
                )
        self._fd.write("    </osmand:points_groups>\n  </extensions>\n</gpx>")
        self._fd.close()
