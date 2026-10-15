"""Calcula las reseñas más vistas con los contadores públicos de GoatCounter.

Lo ejecuta .github/workflows/masvistas.yml cada pocas horas y guarda masvistas.json,
que la portada lee para pintar el bloque "Más vistas".

Requisito: en GoatCounter, Settings > Site > "Allow adding visitor counts on your website".
Uso local:  python3 .github/scripts/masvistas.py
"""

import datetime
import html
import json
import os
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
    req = urllib.request.Request(url, headers={"User-Agent": "lascontraluces-masvistas/1.0 (+https://lascontraluces.com)",
                                               "Accept": "application/json", "Connection": "close"})
    err = None
    for espera in (0, 5, 20):              # reintentos con pausa creciente
        time.sleep(espera)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.load(r)
            return int(re.sub(r"\D", "", str(data.get("count", "0"))) or 0)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 0                   # todavía sin visitas
            err = "HTTP %s" % e.code
            if e.code == 403:
                break                      # ajuste de GoatCounter desactivado: no tiene sentido reintentar
        except Exception as e:             # noqa: BLE001
            err = str(e)
    print("AVISO: no se pudo leer %s (%s)" % (path, err))
    return None


def api_counts():
    """Visitas de todas las páginas con una sola consulta a la API de GoatCounter (necesita GOATCOUNTER_TOKEN)."""
    token = os.environ.get("GOATCOUNTER_TOKEN", "").strip()
    if not token:
        return None
    fin = datetime.datetime.now(datetime.timezone.utc)
    url = ("https://%s.goatcounter.com/api/v0/stats/hits?start=2020-01-01T00:00:00Z&end=%s&limit=100&daily=false"
           % (CODE, fin.strftime("%Y-%m-%dT%H:%M:%SZ")))
    req = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json",
                                               "User-Agent": "lascontraluces-masvistas/1.0"})
    for espera in (0, 10, 30):
        time.sleep(espera)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
            out = {}
            for h in data.get("hits", []):
                out[h.get("path", "").lstrip("/")] = int(h.get("count", 0))
            return out
        except Exception as e:  # noqa: BLE001
            print("AVISO: la API de GoatCounter falló (%s)" % e)
    return None


def main():
    # Se guardan los contadores de la última vez: si una página falla, conserva su valor anterior.
    previo = {}
    if OUT.exists():
        try:
            previo = json.loads(OUT.read_text(encoding="utf-8")).get("counts", {})
        except Exception:  # noqa: BLE001
            previo = {}
    res, ok, fallos_seguidos = [], 0, 0
    por_api = api_counts()
    if por_api is not None:
        print("Visitas leídas con la API de GoatCounter:", len(por_api), "páginas con visitas")
    todas0 = reviews()
    if por_api is None:
        # Sin API: primero las páginas que aún no tienen contador guardado, así cada ejecución avanza
        # un poco aunque GoatCounter corte conexiones; las que ya tenemos se refrescan al final.
        todas0.sort(key=lambda x: x["href"] in previo)
    inicio = time.time()
    for it in todas0:
        if time.time() - inicio > 600:
            print("Pasados 10 minutos; se corta esta ejecución")
            break
        if por_api is not None:
            n = por_api.get(it["href"], 0)
        else:
            n = views(it["href"])
        if n is None:
            fallos_seguidos += 1
            n = previo.get(it["href"], 0)
            if fallos_seguidos >= 6:
                print("GoatCounter rechaza las consultas; se corta esta ejecución")
                break
        else:
            ok += 1
            fallos_seguidos = 0
        it["count"] = n
        res.append(it)
        if por_api is None:
            time.sleep(2)
    if ok == 0:
        print("No se pudo leer ninguna página; no toco masvistas.json")
        return
    counts = dict(previo)
    counts.update({x["href"]: x["count"] for x in res})
    todas = reviews()
    for x in todas:
        x["count"] = counts.get(x["href"], 0)
    top = sorted((x for x in todas if x["count"] > 0), key=lambda x: -x["count"])[:TOP]
    OUT.write_text(json.dumps({"items": top, "counts": counts}, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")
    print("reseñas leídas:", ok, "de", len(res), "| con visitas:", sum(1 for x in todas if x["count"] > 0))


main()
