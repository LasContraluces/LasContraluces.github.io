"""Descarga el diario de Serializd y guarda las últimas series vistas en serializd.json.

Lo ejecuta la GitHub Action .github/workflows/serializd.yml cada pocas horas.
Serializd no tiene RSS ni permite pedir su API desde el navegador (CORS),
así que el JSON se genera aquí y la portada lo lee como un fichero más de la web.

Uso local para pruebas:  python3 .github/scripts/serializd.py [diario.json]
"""

import json
import re
import sys
import time
import urllib.request
from pathlib import Path

USER = "RemyLebeau33"
COUNT = 4
API = f"https://serializd.onrender.com/api/user/{USER}/diary"
POSTER = "https://image.tmdb.org/t/p/w185"
OUT = Path(__file__).resolve().parents[2] / "serializd.json"


def fetch_diary():
    req = urllib.request.Request(API, headers={
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (lascontraluces.com)",
        # Sin esta cabecera la API responde "Unauthorized"
        "X-Requested-With": "serializd_vercel",
    })
    last_error = None
    # El servidor está en Render y puede tardar en despertar: reintentos con paciencia
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last_error = e
            time.sleep(20 * (attempt + 1))
    raise SystemExit(f"No se pudo leer Serializd: {last_error}")


def slug(name):
    return re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-") or "show"


def pick(diary):
    reviews = sorted(
        diary.get("reviews", []),
        key=lambda r: r.get("backdate") or r.get("dateAdded") or "",
        reverse=True,
    )
    items, seen = [], set()
    for r in reviews:
        show_id = r.get("showId")
        if show_id in seen:
            continue
        seasons = r.get("showSeasons") or []
        season = next((s for s in seasons if s.get("id") == r.get("seasonId")), None)
        poster = (season or {}).get("posterPath") or next(
            (s["posterPath"] for s in seasons if s.get("posterPath") and s.get("seasonNumber")), None
        )
        if not poster:
            continue  # sin póster no pinta nada en la portada

        name = r.get("showName", "")
        url = f"https://www.serializd.com/show/{slug(name)}-{show_id}"
        title = name
        if season:
            url += f"/season/{season['id']}/{season['seasonNumber']}"
            # Para miniseries no tiene sentido poner "T1"
            if (season.get("name") or "").lower().startswith("season"):
                title = f"{name} · T{season['seasonNumber']}"

        items.append({
            "title": title,
            "url": url,
            "poster": POSTER + poster,
            "rating": r.get("rating"),  # sobre 10
        })
        seen.add(show_id)
        if len(items) == COUNT:
            break
    return items


def main():
    if len(sys.argv) > 1:
        diary = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    else:
        diary = fetch_diary()

    items = pick(diary)
    if not items:
        raise SystemExit("El diario no devolvió ninguna serie; no toco serializd.json")

    new = json.dumps({"items": items}, ensure_ascii=False, indent=2) + "\n"
    if OUT.exists() and OUT.read_text(encoding="utf-8") == new:
        print("Sin cambios")
        return
    OUT.write_text(new, encoding="utf-8")
    print("Actualizado:", ", ".join(i["title"] for i in items))


if __name__ == "__main__":
    main()
