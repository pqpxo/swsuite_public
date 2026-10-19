(function () {
    var container = document.getElementById('ping-chart');
    if (!container) return;

    var assetId = container.dataset.assetId;

    fetch('/api/ping-history/' + assetId)
        .then(function (r) { return r.json(); })
        .then(function (records) {
            container.innerHTML = '';

            if (!records.length) {
                container.innerHTML = '<span class="muted-copy">No ping history yet. Checks run on the configured interval.</span>';
                return;
            }

            // Records are newest-first; reverse so chart reads left=old, right=new
            var data = records.slice().reverse();

            var wrap = document.createElement('div');
            wrap.className = 'ping-chart-wrap';

            var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
            var blockW = 12, blockH = 32, gap = 3;
            var total = data.length;
            var svgW = total * (blockW + gap) - gap;
            svg.setAttribute('width', svgW);
            svg.setAttribute('height', blockH);
            svg.setAttribute('viewBox', '0 0 ' + svgW + ' ' + blockH);
            svg.style.display = 'block';

            data.forEach(function (d, i) {
                var color = d.status === 'active' ? '#4ade80'
                    : d.status === 'offline' ? '#f87171'
                    : '#64748b';
                var rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
                rect.setAttribute('x', i * (blockW + gap));
                rect.setAttribute('y', 0);
                rect.setAttribute('width', blockW);
                rect.setAttribute('height', blockH);
                rect.setAttribute('rx', 3);
                rect.setAttribute('fill', color);
                rect.setAttribute('opacity', 0.85);
                var title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
                title.textContent = d.status + ' · ' + d.t.replace('T', ' ').replace('Z', ' UTC');
                rect.appendChild(title);
                svg.appendChild(rect);
            });

            var legend = document.createElement('div');
            legend.className = 'ping-chart-legend';

            var latestStatus = data[data.length - 1].status;
            var latestTime = data[data.length - 1].t.replace('T', ' ').replace('Z', ' UTC');
            var onlineCount = data.filter(function (d) { return d.status === 'active'; }).length;
            var pct = Math.round((onlineCount / data.length) * 100);

            legend.innerHTML =
                '<span class="ping-legend-status ping-legend-' + latestStatus + '">' +
                (latestStatus === 'active' ? 'Online' : latestStatus === 'offline' ? 'Offline' : latestStatus) +
                '</span>' +
                '<span class="ping-legend-uptime">' + pct + '% uptime (' + data.length + ' checks)</span>' +
                '<span class="ping-legend-time">Last checked ' + latestTime + '</span>';

            wrap.appendChild(svg);
            wrap.appendChild(legend);
            container.appendChild(wrap);
        })
        .catch(function () {
            container.innerHTML = '<span class="muted-copy">Could not load ping history.</span>';
        });
})();
