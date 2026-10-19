/* ───────────────────────────────────────────────────────────────────────────
   SWSuite portal configuration.

   mode: 'paths'      — link to /rack, /scan and so on under whatever host
                        the portal is served from. One proxy host in NGINX
                        Proxy Manager covers the whole suite. This is the
                        default, and it works by IP and by domain alike.

         'ports'      — link to this host on each app's published port.
                        Useful for testing an app in isolation, or if you
                        bypass the proxy entirely.

         'subdomains' — link to <sub>.<domain>. Only if you would rather run a
                        proxy host per app.

   The id is internal: it names the /healthz/<id> probe route in the Caddyfile
   and the fallback icon in app.js. Rename an app by changing name and path,
   not id. url, when present, is an external address used as-is in every mode.
   logo is the app's own icon under portal/assets/apps/; leave it out
   and the tile falls back to a generic line icon. repo is the app's GitHub
   URL; leave it out and the panel shows no GitHub button.

   Nothing here needs a rebuild — it is a plain file served as-is. Edit it and
   reload the page.
   ─────────────────────────────────────────────────────────────────────────── */

window.SWSUITE = {

  mode: 'paths',

  apps: [
    {
      id: 'rack',
      repo: 'https://github.com/pqpxo/swrack',
      logo: 'assets/apps/rack.png',
      name: 'SWRack',
      desc: 'Visual rack and data-cabinet documentation',
      port: 8088,
      sub: 'rack',
      path: '/rack'
    },
    {
      id: 'inventory',
      repo: 'https://github.com/pqpxo/swakesop',
      logo: 'assets/apps/inventory.png',
      name: 'SWOps',
      desc: 'Asset inventory, connection trails and QR labels',
      port: 8085,
      sub: 'ops',
      path: '/ops'
    },
    {
      id: 'scan',
      logo: 'assets/apps/scan.png',
      name: 'SWScan',
      desc: 'Video walkthrough to AI vision item catalogue',
      port: 7734,
      sub: 'scan',
      path: '/scan'
    },
    {
      id: 'provision',
      repo: 'https://github.com/pqpxo/swaps',
      logo: 'assets/apps/provision.png',
      name: 'SWAps',
      desc: 'Generate and deploy Linux provisioning over SSH',
      port: 8080,
      sub: 'swaps',
      path: '/swaps'
    },
    {
      id: 'kick',
      repo: 'https://github.com/pqpxo/kicker',
      logo: 'assets/apps/kick.png',
      name: 'SWKick',
      desc: 'Pending apt updates and live upgrades across Linux hosts',
      port: 8000,
      sub: 'kick',
      path: '/kick'
    },
  ]
};
