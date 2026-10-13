#!/usr/bin/env python3
"""SEO y compartir de Las Contraluces. Se puede ejecutar las veces que haga falta.

- Cada reseña: descripción = tagline, imagen para compartir = su portada,
  canonical, og:url, og:type article y enlace al feed.
- Resto de páginas: canonical y enlace al feed.
- Genera sitemap.xml, robots.txt y feed.xml (últimas 30 reseñas, en el orden de la portada, sin fechas: el sitio no guarda la de publicación).
Ejecutar desde la raíz del repo:  python3 .github/scripts/seo.py
"""
import glob, html, os, re, subprocess
from datetime import datetime, timezone

BASE = "https://lascontraluces.com/"
SITE_DESC = "Cine, series, libros y juegos, mirados a contraluz."
FEED_LINK = '<link rel="alternate" type="application/rss+xml" title="Las Contraluces" href="%sfeed.xml">' % BASE


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
    items.append({"cat": cat, "href": href.group(1), "title": title, "tagline": text_of(tt.group(2))})

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
    write(p, s)

# ---- resto de páginas ----
pages = {"index.html": BASE, "cine.html": BASE + "cine.html", "series.html": BASE + "series.html",
         "libros.html": BASE + "libros.html", "juegos.html": BASE + "juegos.html", "podcasts.html": BASE + "podcasts.html"}
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
print("reseñas:", len(items), "| sitemap urls:", len(urls))
