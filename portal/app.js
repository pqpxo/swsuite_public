// version 7
(function () {
  'use strict';
  var REFRESH_MS = 30000;
  var PROBE_TIMEOUT_MS = 6000;
  var cfg = window.SWSUITE || { mode: 'ports', apps: [] };
  var apps = Array.isArray(cfg.apps) ? cfg.apps : [];
  var hostname = window.location.hostname;
  var protocol = window.location.protocol;
  var isIp = /^\d{1,3}(\.\d{1,3}){3}$/.test(hostname) || hostname.indexOf(':') !== -1;
  var useSubdomains = cfg.mode === 'subdomains';
  var usePaths = cfg.mode === 'paths';
  var webOrigin = protocol === 'http:' || protocol === 'https:';
  var subdomainsUsable = useSubdomains && !isIp && hostname.indexOf('.') !== -1;
  var base = hostname.replace(/^portal\./, '');
  var busy = false;
  var tiles = [];
  var ORDER_KEY = 'swsuite.appOrder';
  var reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var meta = {
    rack: { icon: 'server', category: 'Infrastructure' },
    inventory: { icon: 'boxes', category: 'Asset management' },
    scan: { icon: 'scan-line', category: 'AI catalogue' },
    sec: { icon: 'shield-check', category: 'Security' },
    provision: { icon: 'terminal', category: 'Automation' },
    kick: { icon: 'refresh-cw', category: 'Maintenance' },
    print: { icon: 'printer', category: 'Labels' }
  };
  function byId(id) { return document.getElementById(id); }
  function element(tag, className, text) {
    var node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function icon(name) {
    var ns = 'http://www.w3.org/2000/svg';
    var svg = document.createElementNS(ns, 'svg');
    var use = document.createElementNS(ns, 'use');
    svg.setAttribute('class', 'icon');
    svg.setAttribute('aria-hidden', 'true');
    use.setAttribute('href', 'assets/icons.svg#' + name);
    svg.appendChild(use);
    return svg;
  }
  function urlFor(app) {
    if (app.url) return app.url;
    if (!webOrigin) return null;
    // Same origin, same proxy host — whatever hostname and scheme got us here.
    if (usePaths) return app.path;
    if (useSubdomains) {
      if (!subdomainsUsable) return null;
      var port = window.location.port ? ':' + window.location.port : '';
      return protocol + '//' + app.sub + '.' + base + port;
    }
    return protocol + '//' + hostname + ':' + app.port;
  }
  function metadata(app) { return meta[app.id] || { icon: 'layout-grid', category: 'Application' }; }
  // An app's own icon when config.js names one; the generic sprite icon otherwise.
  function artwork(app) {
    if (!app.logo) return icon(metadata(app).icon);
    var img = element('img', 'logo');
    img.src = app.logo;
    img.alt = '';
    img.decoding = 'async';
    return img;
  }
  function select(app, selected) {
    tiles.forEach(function (tile) { tile.button.setAttribute('aria-pressed', String(tile.button === selected)); });
    var details = metadata(app);
    var url = urlFor(app);
    byId('app-category').textContent = details.category;
    byId('app-name').textContent = app.name;
    byId('app-description').textContent = app.desc;
    var repo = byId('repo');
    if (app.repo) {
      repo.href = app.repo;
      repo.setAttribute('aria-label', app.name + ' on GitHub');
      repo.title = app.name + ' on GitHub';
      repo.hidden = false;
    } else {
      repo.hidden = true;
      repo.removeAttribute('href');
      repo.removeAttribute('aria-label');
      repo.removeAttribute('title');
    }
    var art = byId('feature-art');
    art.classList.toggle('has-logo', !!app.logo);
    art.replaceChildren(artwork(app));
    byId('launch-label').textContent = 'Open ' + app.name;
    if (url) {
      byId('launch').href = url;
      byId('launch').removeAttribute('aria-disabled');
    } else {
      byId('launch').removeAttribute('href');
      byId('launch').setAttribute('aria-disabled', 'true');
    }
    byId('feature').hidden = false;
  }
  // ── Tile order ──────────────────────────────────────────────────────────
  // The order is a per-browser preference kept in localStorage: the portal is
  // static files, so there is nowhere server-side to write it. Apps missing from
  // the saved order (newly added to config.js) follow it in config order; ids no
  // longer in config.js are ignored.
  function savedOrder() {
    try {
      var value = JSON.parse(window.localStorage.getItem(ORDER_KEY));
      return Array.isArray(value) ? value : null;
    } catch (e) { return null; }
  }
  function inSavedOrder(list) {
    var saved = savedOrder();
    if (!saved) return list.slice();
    var rank = Object.create(null);
    saved.forEach(function (id, i) { if (typeof id === 'string' && !(id in rank)) rank[id] = i; });
    return list
      .map(function (app, i) { return { app: app, key: app.id in rank ? rank[app.id] : saved.length + i }; })
      .sort(function (a, b) { return a.key - b.key; })
      .map(function (entry) { return entry.app; });
  }
  function saveOrder() {
    var ids = Array.prototype.map.call(byId('apps').children, function (tile) { return tile.dataset.id; });
    try { window.localStorage.setItem(ORDER_KEY, JSON.stringify(ids)); } catch (e) { /* private mode: order lasts this visit only */ }
  }
  var ordered = inSavedOrder(apps);

  ordered.forEach(function (app) {
    var button = element('button', 'app-tile');
    button.type = 'button';
    button.setAttribute('aria-pressed', 'false');
    button.setAttribute('aria-controls', 'feature');
    button.dataset.id = app.id;
    var image = element('span', 'app-icon' + (app.logo ? ' has-logo' : ''));
    image.appendChild(artwork(app));
    var status = element('span', 'status');
    status.dataset.state = 'wait';
    var dot = element('span', 'dot');
    dot.setAttribute('aria-hidden', 'true');
    var label = element('span', '', 'Checking');
    status.append(dot, label);
    button.append(image, element('strong', '', app.name), status);
    button.addEventListener('click', function () { select(app, button); });
    byId('apps').appendChild(button);
    tiles.push({ app: app, button: button, status: status, label: label });
  });
  if (ordered.length) select(ordered[0], tiles[0].button);
  // ── Rearrange mode ──────────────────────────────────────────────────────
  // The pencil button toggles it. Tiles are then dragged with pointer events
  // (mouse, pen and touch alike), or moved with the arrow keys when focused.
  var container = byId('apps');
  var toggle = byId('edit-order');
  var toggleIcon = toggle.querySelector('use');
  var announcer = byId('order-status');
  var editing = false;
  var drag = null;
  var swallowClick = false;

  function setEditing(on) {
    editing = on;
    container.classList.toggle('is-editing', on);
    toggle.setAttribute('aria-pressed', String(on));
    var label = on ? 'Done rearranging' : 'Rearrange applications';
    toggle.setAttribute('aria-label', label);
    toggle.title = label;
    toggleIcon.setAttribute('href', 'assets/icons.svg#' + (on ? 'check' : 'pencil'));
    tiles.forEach(function (tile) {
      if (on) tile.button.setAttribute('aria-describedby', 'order-hint');
      else tile.button.removeAttribute('aria-describedby');
    });
    if (!on && drag) endDrag(false);
  }
  toggle.addEventListener('click', function () { setEditing(!editing); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && editing) { setEditing(false); toggle.focus(); }
  });

  // Runs mutate(), then slides every other tile from where it was to where it
  // now is (FLIP), so neighbours glide aside instead of jumping.
  function reflow(mutate, skip) {
    var kids = Array.prototype.slice.call(container.children);
    var before = kids.map(function (kid) { return kid.getBoundingClientRect(); });
    mutate();
    if (reducedMotion || !Element.prototype.animate) return;
    kids.forEach(function (kid, i) {
      if (kid === skip) return;
      var after = kid.getBoundingClientRect();
      var dx = before[i].left - after.left;
      var dy = before[i].top - after.top;
      if (dx || dy) {
        kid.animate([{ transform: 'translate(' + dx + 'px,' + dy + 'px)' }, { transform: 'none' }],
          { duration: 180, easing: 'cubic-bezier(.2,.7,.3,1)' });
      }
    });
  }
  function position(tile) {
    return Array.prototype.indexOf.call(container.children, tile);
  }
  function announce(tile) {
    var name = tile.querySelector('strong').textContent;
    announcer.textContent = name + ', position ' + (position(tile) + 1) + ' of ' + container.children.length;
  }

  // Keeps the dragged tile under the pointer: its layout slot changes as it
  // passes its neighbours, so the offset is recomputed from that slot each time.
  function follow(x, y) {
    var tile = drag.tile;
    var slotX = container.getBoundingClientRect().left + tile.offsetLeft;
    var slotY = container.getBoundingClientRect().top + tile.offsetTop;
    tile.style.transform = 'translate(' + (x - drag.grabX - slotX) + 'px,' + (y - drag.grabY - slotY) + 'px) scale(1.04)';
  }
  // The tile whose layout box contains the point, by layout position rather
  // than on-screen position, so neighbours mid-animation do not flicker.
  function tileAt(x, y) {
    var box = container.getBoundingClientRect();
    var px = x - box.left, py = y - box.top;
    for (var i = 0; i < container.children.length; i++) {
      var kid = container.children[i];
      if (px >= kid.offsetLeft && px < kid.offsetLeft + kid.offsetWidth &&
          py >= kid.offsetTop && py < kid.offsetTop + kid.offsetHeight) return kid;
    }
    return null;
  }

  container.addEventListener('pointerdown', function (e) {
    if (!editing || drag || (e.pointerType === 'mouse' && e.button !== 0)) return;
    var tile = e.target.closest('.app-tile');
    if (!tile) return;
    var box = container.getBoundingClientRect();
    drag = {
      tile: tile, pointer: e.pointerId, startX: e.clientX, startY: e.clientY, moved: false,
      grabX: e.clientX - (box.left + tile.offsetLeft),
      grabY: e.clientY - (box.top + tile.offsetTop)
    };
    tile.setPointerCapture(e.pointerId);
  });
  container.addEventListener('pointermove', function (e) {
    if (!drag || e.pointerId !== drag.pointer) return;
    if (!drag.moved) {
      if (Math.abs(e.clientX - drag.startX) + Math.abs(e.clientY - drag.startY) < 6) return;
      drag.moved = true;
      drag.tile.classList.add('is-dragging');
    }
    e.preventDefault();
    var over = tileAt(e.clientX, e.clientY);
    if (over && over !== drag.tile) {
      var forward = position(over) > position(drag.tile);
      reflow(function () {
        container.insertBefore(drag.tile, forward ? over.nextSibling : over);
      }, drag.tile);
    }
    follow(e.clientX, e.clientY);
  });
  function endDrag(commit) {
    var tile = drag.tile;
    var moved = drag.moved;
    drag = null;
    tile.classList.remove('is-dragging');
    var from = tile.style.transform;
    tile.style.transform = '';
    if (moved) {
      if (from && !reducedMotion && Element.prototype.animate) {
        tile.animate([{ transform: from }, { transform: 'none' }], { duration: 160, easing: 'ease-out' });
      }
      swallowClick = true;
      setTimeout(function () { swallowClick = false; }, 0);
      if (commit) { saveOrder(); announce(tile); }
    }
  }
  container.addEventListener('pointerup', function (e) {
    if (drag && e.pointerId === drag.pointer) endDrag(true);
  });
  container.addEventListener('pointercancel', function (e) {
    if (drag && e.pointerId === drag.pointer) endDrag(true);
  });
  // A drag ends with a click on the tile; it should not also select it.
  container.addEventListener('click', function (e) {
    if (swallowClick) { e.stopPropagation(); e.preventDefault(); swallowClick = false; }
  }, true);

  container.addEventListener('keydown', function (e) {
    if (!editing) return;
    var tile = e.target.closest('.app-tile');
    if (!tile) return;
    var count = container.children.length;
    var from = position(tile);
    var to = { ArrowLeft: from - 1, ArrowUp: from - 1, ArrowRight: from + 1, ArrowDown: from + 1, Home: 0, End: count - 1 }[e.key];
    if (to === undefined) return;
    e.preventDefault();
    to = Math.max(0, Math.min(count - 1, to));
    if (to === from) return;
    reflow(function () {
      var others = Array.prototype.filter.call(container.children, function (kid) { return kid !== tile; });
      container.insertBefore(tile, others[to] || null);
    });
    tile.focus();
    saveOrder();
    announce(tile);
  });

  function note(message) { byId('note').textContent = message; byId('note').hidden = false; }
  if (!apps.length) {
    note('No applications are configured. Add them to config.js and reload the page.');
  } else if (!webOrigin) {
    note('Serve these files from your existing portal web server. Opening index.html directly cannot check your applications or build their server addresses.');
  } else if (useSubdomains && !subdomainsUsable) {
    note('Subdomain links require a domain name. Browse the portal by its hostname, or set mode to ports in config.js.');
  }
  function probe(id) {
    var url = '/healthz/' + encodeURIComponent(id);
    function request(method) {
      var controller = new AbortController();
      var timer = setTimeout(function () { controller.abort(); }, PROBE_TIMEOUT_MS);
      return fetch(url, { method: method, cache: 'no-store', signal: controller.signal })
        .then(function (res) { clearTimeout(timer); return res; }, function (err) { clearTimeout(timer); throw err; });
    }
    return request('HEAD')
      .then(function (res) { return res.status === 405 || res.status === 501 ? request('GET') : res; })
      .then(function (res) { return res.ok; })
      .catch(function () { return false; });
  }
  function refresh() {
    if (busy || !webOrigin || !tiles.length) return;
    busy = true;
    tiles.forEach(function (tile) { tile.status.dataset.state = 'wait'; tile.label.textContent = 'Checking'; });
    Promise.all(tiles.map(function (tile) {
      return probe(tile.app.id).then(function (ok) {
        tile.status.dataset.state = ok ? 'up' : 'down';
        tile.label.textContent = ok ? 'Online' : 'Unavailable';
        return ok;
      });
    })).finally(function () { busy = false; });
  }
  if (!webOrigin && apps.length) {
    tiles.forEach(function (tile) { tile.label.textContent = 'Not checked'; });
  }
  refresh();
  setInterval(refresh, REFRESH_MS);
  document.addEventListener('visibilitychange', function () { if (document.visibilityState === 'visible') refresh(); });
})();
