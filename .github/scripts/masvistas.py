"""Calcula las reseñas más vistas con los contadores públicos de GoatCounter.

Lo ejecuta .github/workflows/masvistas.yml cada pocas horas y guarda masvistas.json,
que la portada lee para pintar el bloque "Más vistas".

Requisito: en GoatCounter, Settings > Site > "Allow adding visitor counts on your website".
Uso local:  python3 .github/scripts/masvistas.py
"""

import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CODE = "lascontraluces"
TOP = 5
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "masvistas.json"

def text_of(x):
    return html.unescape(re.sub(r"<[^>]+>", "", x)).strip()


def reviews():
    idx = (ROOT / "index.html").read_text(encoding="utf-8")
    idx = idx[idx.index('<ul class="review-list"'):]
    out = []
    for m in re.finditer(r'<li class="cat-(\w+)">(.*?)</li>', idx, re.S):
        cat, body = m.groups()
        href = re.search(r'href="(reviews/[^"]+)"', body)
        tt = re.search(r'<span class="title">(.*?)</span>\s*<span class="tagline">', body, re.S)
        if not (href and tt):
            continue
        ym = re.search(r'<span class="year">(.*?)</span>', tt.group(1), re.S)
        year = text_of(ym.group(1)) if ym else ""
        raw = re.sub(r'<span class="cat-tag">.*?</span>', "", tt.group(1), flags=re.S)
        raw = re.sub(r'<span class="year">.*?</span>', "", raw, flags=re.S)
        out.append({"cat": cat, "href": href.group(1), "name": text_of(raw), "year": year})
    return out


def views(path):
    url = "https://%s.goatcounter.com/counter/%s.json" % (CODE, urllib.parse.quote("/" + path, safe="/"))
    req = urllib.request.Request(url, headers={"User-Agent": "lascontraluces.com masvistas"})
    for intento in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.load(r)
            return int(re.sub(r"\D", "", str(data.get("count", "0"))) or 0)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 0          # todavía sin visitas
            if e.code == 403:
                sys.exit("403: activa 'Allow adding visitor counts on your website' en GoatCounter")
            time.sleep(2)
        except Exception:
            time.sleep(2)
    return None


def main():
    res = []
    for it in reviews():
        n = views(it["href"])
        if n is None:
            sys.exit("No se pudo leer GoatCounter; no toco masvistas.json")
        it["count"] = n
        res.append(it)
        time.sleep(0.3)
    res.sort(key=lambda x: -x["count"])
    top = [x for x in res if x["count"] > 0][:TOP]
    OUT.write_text(json.dumps({"items": top}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("reseñas leídas:", len(res), "| con visitas:", sum(1 for x in res if x["count"] > 0))


main()
