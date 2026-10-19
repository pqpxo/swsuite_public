(function () {
    if (!('Notification' in window)) return;

    var STORAGE_KEY = 'swakesops_ping_statuses';
    var POLL_MS = 30000;
    var btn = document.getElementById('enable-notifications-btn');

    function syncButtonVisibility() {
        if (!btn) return;
        btn.hidden = Notification.permission !== 'default';
    }

    function poll() {
        fetch('/api/ping-status')
            .then(function (r) { return r.json(); })
            .then(function (devices) {
                var previous = {};
                try { previous = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); } catch (_) {}

                var current = {};
                devices.forEach(function (d) {
                    current[d.id] = d.status;
                    var prev = previous[d.id];
                    if (!prev || prev === d.status) return;
                    if (d.status === 'offline') {
                        new Notification('Device offline — ' + d.name, {
                            body: d.ip + ' is no longer responding.',
                            icon: '/static/logo.png',
                            tag: 'ping-' + d.id,
                        });
                    } else if (d.status === 'active' && prev === 'offline') {
                        new Notification('Device back online — ' + d.name, {
                            body: d.ip + ' is responding again.',
                            icon: '/static/logo.png',
                            tag: 'ping-' + d.id,
                        });
                    }
                });

                localStorage.setItem(STORAGE_KEY, JSON.stringify(current));
            })
            .catch(function () {});
    }

    function startPolling() {
        poll();
        setInterval(poll, POLL_MS);
    }

    if (btn) {
        btn.addEventListener('click', function () {
            Notification.requestPermission().then(function () {
                syncButtonVisibility();
                if (Notification.permission === 'granted') startPolling();
            });
        });
    }

    syncButtonVisibility();

    if (Notification.permission === 'granted') {
        startPolling();
    }
})();
