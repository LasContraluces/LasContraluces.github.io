"""Guarda las últimas películas vistas en Letterboxd en letterboxd.json.

Lo ejecuta .github/workflows/letterboxd.yml cada hora. La portada lee ese fichero y,
si no existe o está vacío, vuelve a pedir el RSS a rss2json como antes.

Uso local:  python3 .github/scripts/letterboxd.py [rss.xml]
"""

import html
import json
import re
import sys
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

USER = "remylebeau33"
COUNT = 4
FEED = f"https://letterboxd.com/{USER}/rss/"
OUT = Path(__file__).resolve().parents[2] / "letterboxd.json"


def fetch():
    req = urllib.request.Request(FEED, headers={
        "User-Agent": "Mozilla/5.0 (compatible; lascontraluces.com)",
        "Accept": "application/rss+xml, application/xml, text/xml",
    })
    last = None
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(10 * (attempt + 1))
    raise SystemExit(f"No se pudo leer el RSS de Letterboxd: {last}")


def pick(xml_text):
    root = ET.fromstring(xml_text)
    items = []
    for it in root.iter("item"):
        link = (it.findtext("link") or "").strip()
        if "/film/" not in link:
            continue  # listas y reseñas sin película
        desc = it.findtext("description") or ""
        m = re.search(r'src="([^"]+)"', desc)
        if not m:
            continue
        items.append({
            "title": html.unescape((it.findtext("title") or "").strip()),
            "url": link,
            "poster": html.unescape(m.group(1)),
        })
        if len(items) == COUNT:
            break
    return items


def main():
    xml_text = Path(sys.argv[1]).read_text(encoding="utf-8") if len(sys.argv) > 1 else fetch()
    items = pick(xml_text)
    if not items:
        raise SystemExit("El RSS no trajo películas; no toco letterboxd.json")
    new = json.dumps({"items": items}, ensure_ascii=False, indent=2) + "\n"
    if OUT.exists() and OUT.read_text(encoding="utf-8") == new:
        print("Sin cambios")
        return
    OUT.write_text(new, encoding="utf-8")
    print("Actualizado:", ", ".join(i["title"] for i in items))


if __name__ == "__main__":
    main()
