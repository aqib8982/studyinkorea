/* Study In Korea: page switching, deadlines, course search, menu, pop-up and motion.
   Everything on the page is readable without this script; it only adds behaviour. */
(function () {
  'use strict';
  var $ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };
  var byId = function (id) { return document.getElementById(id); };
  var reduceMotion = window.matchMedia && matchMedia('(prefers-reduced-motion:reduce)').matches;
  document.documentElement.classList.add('js');

  /* ---------- deadlines: "N days left", "Today", "Date passed" from the visitor's date ---------- */
  var now = new Date();
  var today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  function daysLeft(iso) {
    var p = (iso || '').split('-');
    if (p.length < 3) return null;
    return Math.round((new Date(+p[0], +p[1] - 1, +p[2]) - today) / 864e5);
  }
  $('.dl[data-date]').forEach(function (el) {
    var n = daysLeft(el.getAttribute('data-date'));
    if (n === null) return;
    var flag = document.createElement('span');
    flag.className = 'flag ' + (n < 0 ? 'past' : 'soon');
    flag.textContent = n < 0 ? 'Date passed' : n === 0 ? 'Today' : n === 1 ? '1 day left' : n + ' days left';
    if (n < 0) el.classList.add('past');
    el.appendChild(document.createTextNode(' '));
    el.appendChild(flag);
  });
  // Lists marked data-passed-last keep their order, but entries whose deadline has passed move to the end.
  $('[data-passed-last]').forEach(function (list) {
    var items = Array.prototype.slice.call(list.children);
    var passed = items.filter(function (it) {
      var d = it.getAttribute('data-date') || (it.querySelector('.dl[data-date]') || {getAttribute: function () { return ''; }}).getAttribute('data-date');
      var n = daysLeft(d);
      return n !== null && n < 0;
    });
    passed.forEach(function (it) { list.appendChild(it); });
  });

  /* ---------- reveal on scroll (content stays visible if this cannot run) ---------- */
  var REVEAL = '.band .wrap > h2, .band .wrap > .kick, .band .wrap > .bsub, .band .wrap > .subh, .bhead, .hwc, .hownote, ' +
    '.steps li, .req, .vcard, .ctcard, .searchbar, .about .wrap > *, .tiles > .tile, .page > .wrap > .uni, .vid, .card, ' +
    '.cities > div, .cbox';
  var io = null;
  function revealed(el) {
    var delay = parseFloat(el.style.transitionDelay) || 0;
    el.classList.add('in');
    setTimeout(function () { el.classList.remove('rv', 'in'); el.style.transitionDelay = ''; }, 1100 + delay);
  }
  function reveal() {
    if (!('IntersectionObserver' in window) || reduceMotion) return;
    if (!io) {
      io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { if (e.isIntersecting || e.boundingClientRect.bottom < 0) { io.unobserve(e.target); revealed(e.target); } });
      }, {rootMargin: '0px 0px -8% 0px', threshold: 0.05});
    }
    var page = document.querySelector('.page.on'), inView = [];
    $(REVEAL, page).forEach(function (el) {
      if (el.hasAttribute('data-rv')) return;
      el.setAttribute('data-rv', '1');
      var k = Array.prototype.indexOf.call(el.parentNode.children, el);
      el.style.transitionDelay = (k % 4) * 80 + 'ms';
      el.classList.add('rv');
      var r = el.getBoundingClientRect();
      if (r.top < innerHeight * 0.92 && r.bottom > 0) inView.push(el); else io.observe(el);
    });
    requestAnimationFrame(function () { requestAnimationFrame(function () { inView.forEach(revealed); }); });
    // safety net: anything on screen or above it that has not appeared after 1.5 s is shown
    setTimeout(function () {
      $('.rv:not(.in)', page).forEach(function (el) {
        var r = el.getBoundingClientRect();
        if (r.top < innerHeight) { io.unobserve(el); revealed(el); }  // on screen, or already scrolled past
      });
    }, 1500);
  }
  function resetReveal(page) {
    $('[data-rv]', page).forEach(function (el) {
      el.removeAttribute('data-rv');
      el.classList.remove('rv', 'in');
      el.style.transitionDelay = '';
      if (io) io.unobserve(el);
    });
  }

  /* ---------- YouTube pop-up: closable, returns on the next page, hidden over the footer ---------- */
  var pop = byId('ytpop');
  byId('ytx').addEventListener('click', function () { pop.classList.add('hide'); });
  function showPop() {
    pop.classList.remove('hide');
    pop.style.animation = 'none';
    void pop.offsetWidth; // restart the slide-in
    pop.style.animation = '';
  }
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { pop.classList.toggle('atfoot', e.isIntersecting); });
    }, {threshold: 0.15}).observe(byId('site-footer'));
  }

  /* ---------- pages: one section per address (#home, #uni-sejong-masters, ...) ---------- */
  var current = null;
  function show(name, initial) {
    var page = byId('p-' + name);
    if (!page) { name = 'home'; page = byId('p-home'); }
    if (current === name) return;
    current = name;
    showPop();
    $('.page').forEach(function (p) { p.classList.toggle('on', p === page); });
    var nav = page.getAttribute('data-nav');
    $('.nav nav a').forEach(function (a) {
      if (a.getAttribute('data-n') === nav) a.setAttribute('aria-current', 'page');
      else a.removeAttribute('aria-current');
    });
    if (!initial) {
      window.scrollTo(0, 0);
      try { page.setAttribute('tabindex', '-1'); page.focus({preventScroll: true}); } catch (e) {}
    }
    resetReveal(page);
    setTimeout(reveal, 30);
  }
  function fromHash() { return (location.hash || '').replace(/^#/, '') || 'home'; }
  document.addEventListener('click', function (e) {
    var a = e.target.closest ? e.target.closest('a[href^="#"]') : null;
    if (!a) return;
    var name = a.getAttribute('href').slice(1);
    if (!byId('p-' + name)) return;
    e.preventDefault();
    try { if (fromHash() !== name) location.hash = name; } catch (err) {}
    show(name);
  });
  window.addEventListener('hashchange', function () { show(fromHash()); });
  show(fromHash(), true);

  /* ---------- footer year ---------- */
  var year = byId('fyear');
  if (year) year.textContent = new Date().getFullYear();

  /* ---------- mobile menu (below 1040px) ---------- */
  var navBar = document.querySelector('.nav'), toggle = byId('navtog');
  function setMenu(open) {
    navBar.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
  }
  toggle.addEventListener('click', function () { setMenu(!navBar.classList.contains('open')); });
  $('#navlinks a').forEach(function (a) { a.addEventListener('click', function () { setMenu(false); }); });

  /* ---------- course search: text, location and degree filters ---------- */
  var state = {city: '', lvl: '', q: ''};
  var rows = $('.crs'), total = rows.length;
  var names = $('.crs .pn, .crs .pm');
  names.forEach(function (n) { n.setAttribute('data-o', n.textContent); });
  function esc(s) { return s.replace(/[&<>]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;'}[c]; }); }
  function apply() {
    var shown = 0, q = state.q.trim().toLowerCase();
    rows.forEach(function (row) {
      var ok = (!state.city || row.getAttribute('data-city') === state.city) &&
        (!state.lvl || (' ' + row.getAttribute('data-tags') + ' ').indexOf(' ' + state.lvl + ' ') > -1) &&
        (!q || row.getAttribute('data-t').indexOf(q) > -1);
      row.classList.toggle('hide', !ok);
      if (ok) shown++;
    });
    names.forEach(function (n) {
      var o = n.getAttribute('data-o'), i = q ? o.toLowerCase().indexOf(q) : -1;
      if (i < 0) n.textContent = o;
      else n.innerHTML = esc(o.slice(0, i)) + '<mark>' + esc(o.slice(i, i + q.length)) + '</mark>' + esc(o.slice(i + q.length));
    });
    byId('count').textContent = shown === total ? total + ' courses' : shown + ' of ' + total + ' courses';
    byId('none').classList.toggle('hide', shown > 0);
  }
  function press(row, btn) { $('.chip', row).forEach(function (b) { b.setAttribute('aria-pressed', b === btn ? 'true' : 'false'); }); }
  $('#cityrow .chip').forEach(function (b) {
    b.addEventListener('click', function () { state.city = b.getAttribute('data-city'); press(b.parentNode, b); apply(); });
  });
  $('#lvlrow .chip').forEach(function (b) {
    b.addEventListener('click', function () { state.lvl = b.getAttribute('data-lvl'); press(b.parentNode, b); apply(); });
  });
  $('#cityrow .chip, #lvlrow .chip').forEach(function (b) { if (!b.hasAttribute('aria-pressed')) b.setAttribute('aria-pressed', 'false'); });
  byId('q').addEventListener('input', function (e) { state.q = e.target.value; apply(); });
  apply();
})();
