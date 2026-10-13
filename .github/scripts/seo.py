#!/usr/bin/env python3
"""Mantenimiento de Las Contraluces. Se puede ejecutar las veces que haga falta.

Fuentes de datos (en .github/scripts/):
  notas.json  nota de cada reseña sobre 10 con decimales  {"slug": 8.8, ...}
  top.json    lista ordenada de slugs del top 10, en el orden que se quiera

Qué hace:
- Nota numérica junto a las estrellas en todas las páginas. Si la reseña está en notas.json
  se usa esa nota (y el relleno de las estrellas la sigue); si no, se deduce del relleno actual.
- Enlace "Top 10" en la navegación, página top.html y bloque "Mi top 5" en la portada.
- Cada reseña: descripción = tagline, imagen para compartir = su portada, canonical,
  og:url, og:type article y enlace al feed.
- Final de cada reseña: bloque "Más reseñas de [categoría]" (las 3 últimas de su categoría).
- Resto de páginas: canonical y enlace al feed.
- Genera sitemap.xml, robots.txt y feed.xml (últimas 30 reseñas, en el orden de la portada,
  sin fechas: el sitio no guarda la de publicación).
Ejecutar desde la raíz del repo:  python3 .github/scripts/seo.py
"""
import glob, html, json, os, re, subprocess
from datetime import datetime, timezone

BASE = "https://lascontraluces.com/"
SITE_DESC = "Cine, series, libros y juegos, mirados a contraluz."
FEED_LINK = '<link rel="alternate" type="application/rss+xml" title="Las Contraluces" href="%sfeed.xml">' % BASE
NOTAS_FILE = ".github/scripts/notas.json"
TOP_FILE = ".github/scripts/top.json"
NOTAS = json.load(open(NOTAS_FILE, encoding="utf-8")) if os.path.exists(NOTAS_FILE) else {}
TOP = json.load(open(TOP_FILE, encoding="utf-8")) if os.path.exists(TOP_FILE) else []


def git(*args):
    r = subprocess.run(["git"] + list(args), capture_output=True, text=True)
    return r.stdout.strip()


def last_date(path):
    out = git("log", "-1", "--format=%aI", "--", path)
    return datetime.fromisoformat(out) if out else datetime.fromtimestamp(os.path.getmtime(path), timezone.utc)


def text_of(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def attr(v):
    return html.escape(v, quote=True)


def set_meta(s, key, name, value):
    pat = re.compile(r'<meta %s="%s" content="[^"]*">' % (key, re.escape(name)))
    tag = '<meta %s="%s" content="%s">' % (key, name, attr(value))
    if pat.search(s):
        return pat.sub(lambda m: tag, s, count=1)
    return s  # si no existe, se añade con add_after


def add_after(s, anchor_pat, tag):
    m = re.search(anchor_pat, s)
    return s[:m.end()] + "\n" + tag + s[m.end():] if m else s


def add_head_links(s, url):
    if 'rel="canonical"' not in s:
        s = s.replace('<link rel="stylesheet"', '<link rel="canonical" href="%s">\n<link rel="stylesheet"' % url, 1)
    if 'application/rss+xml' not in s:
        s = s.replace('<link rel="stylesheet"', FEED_LINK + '\n<link rel="stylesheet"', 1)
    return s


def write(path, s):
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)


# ---- nota numérica junto a las estrellas + enlace "Top 10" en la navegación ----
UNWRAP_RE = re.compile(
    r'<(span|div) class="score"><span class="nota"[^>]*>[^<]*<small>/10</small></span>'
    r'(<(?:span|div) class="(?:stars|meta)"[^>]*>★★★★★</(?:span|div)>)</\1>')
STAR_RE = re.compile(
    r'<(span|div) class="(stars|meta)" (style="background-image:linear-gradient\(90deg,var\(--star-color\) ([\d.]+)%,transparent [\d.]+%\)")'
    r'(?: role="img" aria-label="[^"]*")?>★★★★★</\1>')
LI_RE = re.compile(r'<li class="cat-\w+">.*?</li>', re.S)
NAV_RE = re.compile(r'(<a href="((?:\.\./|/)?)juegos\.html"[^>]*>Juegos</a>)')


def fmt_nota(n):
    n = round(float(n), 1)
    return ("%d" % n) if n == int(n) else ("%.1f" % n).replace(".", ",")


def fmt_pct(n):
    p = round(float(n) * 10, 1)
    return ("%d" % p) if p == int(p) else ("%.1f" % p)


def add_score(m, nota=None):
    tag, cls = m.group(1), m.group(2)
    if nota is None:
        nota = float(m.group(4)) / 10
    n, p = fmt_nota(nota), fmt_pct(nota)
    style = 'style="background-image:linear-gradient(90deg,var(--star-color) %s%%,transparent %s%%)"' % (p, p)
    return ('<%s class="score"><span class="nota" aria-hidden="true">%s<small>/10</small></span>'
            '<%s class="%s" %s role="img" aria-label="%s de 10">★★★★★</%s></%s>') % (tag, n, tag, cls, style, n, tag, tag)


def add_nav(t):
    if re.search(r'<a href="[^"]*top\.html"[^>]*>Top 10</a>', t):
        return t
    return NAV_RE.sub(lambda m: m.group(1) + '\n    <a href="%stop.html" class="">Top 10</a>' % m.group(2), t, count=1)


for f in glob.glob("*.html") + glob.glob("reviews/*.html"):
    t = open(f, encoding="utf-8").read()
    raw = UNWRAP_RE.sub(lambda m: m.group(2), t)
    if f.startswith("reviews/"):
        slug = os.path.basename(f)[:-5]
        # en la propia reseña solo la cabecera (.meta) usa su nota; las filas "Más reseñas" se rehacen luego
        t2 = STAR_RE.sub(lambda m, s=slug: add_score(m, NOTAS.get(s) if m.group(2) == "meta" else None), raw)
    else:
        def sub_li(lm):
            hm = re.search(r'href="reviews/([^"/]+)\.html"', lm.group(0))
            nota = NOTAS.get(hm.group(1)) if hm else None
            return STAR_RE.sub(lambda m: add_score(m, nota), lm.group(0))
        t2 = LI_RE.sub(sub_li, raw)
    if TOP:
        t2 = add_nav(t2)
    if t2 != t:
        write(f, t2)

# ---- lista de reseñas, en el orden de la portada ----
idx = open("index.html", encoding="utf-8").read()
start = idx.index('<ul class="review-list"')
items = []
for m in re.finditer(r'<li class="cat-(\w+)">(.*?)</li>', idx[start:], re.S):
    cat, body = m.group(1), m.group(2)
    href = re.search(r'href="(reviews/[^"]+)"', body)
    tt = re.search(r'<span class="title">(.*?)</span>\s*<span class="tagline">(.*?)</span>', body, re.S)
    if not (href and tt):
        continue
    cat_tag = re.search(r'<span class="cat-tag">(.*?)</span>', tt.group(1))
    title = text_of(tt.group(1))
    if cat_tag:
        title = title[len(text_of(cat_tag.group(1))):].strip()
    ym = re.search(r'<span class="year">(.*?)</span>', body, re.S)
    year = text_of(ym.group(1)) if ym else ""
    name = title[:-len(year)].strip() if year and title.endswith(year) else title
    nm = re.search(r'class="nota"[^>]*>([\d,]+)<small>', body)
    items.append({"li": m.group(0), "cat": cat, "href": href.group(1), "slug": os.path.basename(href.group(1))[:-5],
                  "title": title, "name": name, "year": year, "nota": nm.group(1) if nm else "",
                  "tagline": text_of(tt.group(2))})


LABELS = {
    "cine": ("cine", "Ver todo el cine"),
    "series": ("series", "Ver todas las series"),
    "libros": ("libros", "Ver todos los libros"),
    "juegos": ("juegos", "Ver todos los juegos"),
}
RELATED_RE = re.compile(r"<!-- related:start -->.*?<!-- related:end -->\n?", re.S)


def related_block(it):
    otros = [o for o in items if o["cat"] == it["cat"] and o["href"] != it["href"]][:3]
    if not otros or it["cat"] not in LABELS:
        return ""
    nombre, ver = LABELS[it["cat"]]
    lis = []
    for o in otros:
        li = re.sub(r">\s+<", "><", o["li"]).strip()
        li = li.replace('href="reviews/', 'href="').replace('src="images/', 'src="../images/')
        lis.append(li)
    return ('<!-- related:start -->\n<section class="related %s">\n  <h2 class="sec-title">Más reseñas de %s</h2>\n'
            '  <ul class="review-list">\n%s\n  </ul>\n  <p class="related-more"><a href="../%s.html">%s →</a></p>\n'
            '</section>\n<!-- related:end -->\n') % (it["cat"], nombre, "\n".join(lis), it["cat"], ver)


# ---- páginas de reseña ----
for it in items:
    p = it["href"]
    s = open(p, encoding="utf-8").read()
    url = BASE + p
    tg = re.search(r'<p class="tagline">(.*?)</p>', s, re.S)
    desc = text_of(tg.group(1)) if tg else it["tagline"]
    img = re.search(r'<img class="review-image" src="\.\./(images/[^"]+)"', s)
    if img and os.path.exists(img.group(1)):
        image = BASE + img.group(1)
        s = set_meta(s, "property", "og:image", image)
        s = set_meta(s, "name", "twitter:image", image)
    s = set_meta(s, "name", "description", desc)
    s = set_meta(s, "property", "og:description", desc)
    s = set_meta(s, "property", "og:type", "article")
    if 'name="twitter:description"' in s:
        s = set_meta(s, "name", "twitter:description", desc)
    else:
        s = add_after(s, r'<meta name="twitter:title" content="[^"]*">', '<meta name="twitter:description" content="%s">' % attr(desc))
    if 'property="og:url"' in s:
        s = set_meta(s, "property", "og:url", url)
    else:
        s = add_after(s, r'<meta property="og:type" content="[^"]*">', '<meta property="og:url" content="%s">' % url)
    s = add_head_links(s, url)
    block = related_block(it)
    if RELATED_RE.search(s):
        s = RELATED_RE.sub(lambda m: block, s, count=1)
    elif block:
        s = s.replace("</article>", "</article>\n" + block.rstrip("\n"), 1)
    write(p, s)

# ---- Top 10: página top.html y bloque "Mi top 5" en la portada ----
by_slug = {it["slug"]: it for it in items}
missing = [s for s in TOP if s not in by_slug]
if missing:
    print("AVISO: slugs de top.json que no existen:", missing)
top_items = [by_slug[s] for s in TOP if s in by_slug]

if top_items and os.path.exists("libros.html"):
    rows = []
    for i, it in enumerate(top_items, 1):
        li = re.sub(r">\s+<", "><", it["li"]).strip()
        li = re.sub(r'(<a class="row" href="[^"]+">)', lambda m, n=i: m.group(1) + '<span class="rk">%d</span>' % n, li, count=1)
        rows.append(li)
    s = open("libros.html", encoding="utf-8").read()
    s = s.replace("Libros — Las Contraluces", "Top 10 — Las Contraluces")
    s = s.replace('href="%slibros.html"' % BASE, 'href="%stop.html"' % BASE)
    s = s.replace('class="active libros"', 'class=""')
    s = s.replace('<a href="top.html" class="">Top 10</a>', '<a href="top.html" class="active top">Top 10</a>')
    desc = "Mi top 10: lo mejor que he visto y leído desde que empezó el blog, con nota."
    for key, name in (("name", "description"), ("property", "og:description")):
        s = set_meta(s, key, name, desc)
    main = ('<main>\n    <h1 class="top-title">Mi top 10</h1>\n'
            '    <p class="top-intro">Lo mejor que he visto y leído desde que empezó el blog.</p>\n'
            '    <ul class="review-list top-list">\n%s\n    </ul>\n  </main>') % "\n".join(rows)
    s = re.sub(r"<main>.*?</main>", lambda m: main, s, count=1, flags=re.S)
    write("top.html", s)

TOP5_RE = re.compile(r"<!-- top5:start -->.*?<!-- top5:end -->\n?", re.S)


def top5_block():
    lis = []
    for i, it in enumerate(top_items[:5], 1):
        lis.append('<li class="cat-%s"><a href="%s"><span class="top-rk">%d</span><span class="ep-title">%s <span class="year">%s</span></span>'
                   '<span class="top-n">%s</span></a></li>' % (it["cat"], it["href"], i, html.escape(it["name"]), it["year"], it["nota"]))
    return ('<!-- top5:start -->\n<div class="ep-widget top-widget">\n        <div class="lb-label">Mi top 5</div>\n'
            '        <ul class="ep-list">\n          %s\n        </ul>\n        <a class="top-more" href="top.html">Ver el top 10 →</a>\n'
            '      </div>\n      <!-- top5:end -->\n') % "\n          ".join(lis)


s = open("index.html", encoding="utf-8").read()
blk = top5_block() if top_items else ""
if TOP5_RE.search(s):
    s = TOP5_RE.sub(lambda m: blk, s, count=1)
elif blk:
    s = s.replace('<aside class="sidebar">', '<aside class="sidebar">\n      ' + blk, 1)
write("index.html", s)

# ---- resto de páginas ----
pages = {"index.html": BASE, "cine.html": BASE + "cine.html", "series.html": BASE + "series.html",
         "libros.html": BASE + "libros.html", "juegos.html": BASE + "juegos.html", "podcasts.html": BASE + "podcasts.html",
         "top.html": BASE + "top.html"}
for p, url in pages.items():
    if os.path.exists(p):
        write(p, add_head_links(open(p, encoding="utf-8").read(), url))

# ---- sitemap.xml ----
urls = []
for p, url in pages.items():
    if os.path.exists(p):
        urls.append((url, last_date(p)))
for it in items:
    urls.append((BASE + it["href"], last_date(it["href"])))
sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
for u, d in urls:
    sm.append("  <url><loc>%s</loc><lastmod>%s</lastmod></url>" % (html.escape(u), d.date().isoformat()))
sm.append("</urlset>")
write("sitemap.xml", "\n".join(sm) + "\n")

write("robots.txt", "User-agent: *\nAllow: /\n\nSitemap: %ssitemap.xml\n" % BASE)

# ---- feed.xml ----
LABEL = {"cine": "Cine", "series": "Series", "libros": "Libros", "juegos": "Juegos"}
rss = ['<?xml version="1.0" encoding="UTF-8"?>',
       '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">', "<channel>",
       "  <title>Las Contraluces</title>", "  <link>%s</link>" % BASE,
       "  <description>%s</description>" % html.escape(SITE_DESC), "  <language>es</language>",
       '  <atom:link href="%sfeed.xml" rel="self" type="application/rss+xml"/>' % BASE]
for it in items[:30]:
    link = BASE + it["href"]
    rss += ["  <item>", "    <title>%s</title>" % html.escape(it["title"]), "    <link>%s</link>" % link,
            '    <guid isPermaLink="true">%s</guid>' % link,
            "    <category>%s</category>" % LABEL.get(it["cat"], it["cat"]),
            "    <description>%s</description>" % html.escape(it["tagline"]), "  </item>"]
rss += ["</channel>", "</rss>"]
write("feed.xml", "\n".join(rss) + "\n")
print("reseñas:", len(items), "| con nota en notas.json:", sum(1 for it in items if it["slug"] in NOTAS),
      "| top:", len(top_items), "| sitemap urls:", len(urls))
