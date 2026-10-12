/* Buscador de Las Contraluces.
   Lee la lista de reseñas de index.html (siempre al día) y, al escribir,
   descarga también el texto de cada reseña para buscar dentro. */
(function () {
  var me = document.currentScript;
  var root = me.src.replace(/search\.js(\?.*)?$/, '');
  var box = document.getElementById('site-search');
  if (!box) return;
  var input = box.querySelector('input');
  var panel = box.querySelector('.search-results');
  var items = null, loading = null, bodiesDone = false;

  function norm(s) {
    return (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  }

  function loadList() {
    if (loading) return loading;
    loading = fetch(root + 'index.html').then(function (r) { return r.text(); }).then(function (html) {
      var doc = new DOMParser().parseFromString(html, 'text/html');
      items = [];
      doc.querySelectorAll('ul.review-list li').forEach(function (li) {
        var a = li.querySelector('a.row');
        if (!a) return;
        var t = li.querySelector('.title');
        var tag = li.querySelector('.cat-tag');
        var yr = li.querySelector('.year');
        var tg = li.querySelector('.tagline');
        var cat = (li.className.match(/cat-(\w+)/) || [])[1] || '';
        var title = t ? t.textContent.replace(tag ? tag.textContent : '', '').replace(yr ? yr.textContent : '', '').trim() : '';
        items.push({
          url: root + a.getAttribute('href'),
          cat: cat,
          catName: tag ? tag.textContent : '',
          title: title,
          year: yr ? yr.textContent.trim() : '',
          tagline: tg ? tg.textContent.trim() : '',
          body: '',
          key: norm(title + ' ' + (tg ? tg.textContent : '') + ' ' + (tag ? tag.textContent : ''))
        });
      });
      return items;
    });
    return loading;
  }

  function loadBodies() {
    if (bodiesDone) return;
    bodiesDone = true;
    loadList().then(function (list) {
      list.forEach(function (it) {
        fetch(it.url).then(function (r) { return r.text(); }).then(function (html) {
          var doc = new DOMParser().parseFromString(html, 'text/html');
          var b = doc.querySelector('article.review .body');
          it.body = norm(b ? b.textContent : '');
          if (input.value.trim()) run();
        }).catch(function () {});
      });
    });
  }

  function snippet(it, words) {
    // trozo del texto donde aparece la primera palabra, si no está en el título
    if (!it.body) return '';
    for (var i = 0; i < words.length; i++) {
      var p = it.body.indexOf(words[i]);
      if (p > -1 && it.key.indexOf(words[i]) === -1) {
        var from = Math.max(0, p - 40);
        return '…' + it.body.slice(from, p + 70).trim() + '…';
      }
    }
    return '';
  }

  function esc(s) {
    return s.replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; });
  }

  function run() {
    var q = norm(input.value).trim();
    if (!q) { panel.hidden = true; panel.innerHTML = ''; return; }
    if (!items) { loadList().then(run); return; }
    var words = q.split(/\s+/);
    var hits = [];
    items.forEach(function (it) {
      var score = 0;
      for (var i = 0; i < words.length; i++) {
        var w = words[i];
        if (it.key.indexOf(w) > -1) score += 10;
        else if (it.body.indexOf(w) > -1) score += 1;
        else return;
      }
      if (norm(it.title).indexOf(q) > -1) score += 20;
      hits.push({ it: it, score: score });
    });
    hits.sort(function (a, b) { return b.score - a.score; });
    var html = '';
    if (!hits.length) {
      html = '<div class="sr-empty">Nada por aquí con «' + esc(input.value.trim()) + '».</div>';
    } else {
      hits.slice(0, 12).forEach(function (h) {
        var it = h.it, sn = snippet(it, words);
        html += '<a class="sr-item cat-' + it.cat + '" href="' + it.url + '">' +
          '<span class="sr-top"><span class="sr-cat">' + esc(it.catName) + '</span>' +
          '<span class="sr-title">' + esc(it.title) + '</span> <span class="sr-year">' + esc(it.year) + '</span></span>' +
          (sn ? '<span class="sr-snip">' + esc(sn) + '</span>' : (it.tagline ? '<span class="sr-snip">' + esc(it.tagline) + '</span>' : '')) +
          '</a>';
      });
      if (hits.length > 12) html += '<div class="sr-empty">Y ' + (hits.length - 12) + ' más. Afina la búsqueda.</div>';
    }
    panel.innerHTML = html;
    panel.hidden = false;
  }

  input.addEventListener('focus', function () { loadList(); loadBodies(); });
  input.addEventListener('input', run);
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { input.value = ''; run(); input.blur(); }
    if (e.key === 'Enter') { var f = panel.querySelector('a.sr-item'); if (f) location.href = f.href; }
  });
  document.addEventListener('click', function (e) { if (!box.contains(e.target)) panel.hidden = true; });
  input.addEventListener('click', function () { if (input.value.trim()) run(); });
})();
