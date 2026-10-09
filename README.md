# site-monitor

Synthetic uptime + content monitors for every ojardila website, running on
GitHub Actions (outside the home cluster, so a full cluster/home/power
outage still alerts). The in-cluster twin (blackbox exporter, 60 s probes,
Grafana dashboard https://grafana.int.engp.io/d/synthetic-sites) lives in
`ojardila/k8` -> `manifests/blackbox-exporter`.

## Per site (one monitor per site)

Each site repo has:

* `monitor.yaml` - URL, expected `title` (regex), `contains` (strings),
  `selectors` (`#id`, `.class`, `tag`, `tag#id`, `tag.class`), `links`
  (must be present; same-host ones must answer < 400), optional `pages`.
* `.github/workflows/synthetic-monitor.yml` - cron every 5 min, calls
  `.github/workflows/monitor.yml` here.

The check retries 3x (15 s apart). Telegram gets a message only on state
change: `CAIDO: <sitio> ... Desde: <fecha hora> COT` with the failed checks,
and `RECUPERADO: <sitio> ... Volvio: ... (caido desde ...)`. The run also
turns red while the site is down.

Secrets per site repo: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
(ojardila is a user account: there are no org-level secrets).

## Automatic provisioning for new projects

`.github/workflows/provision.yml` (every 30 min + manual) runs
`monitor/provision.py`. Rule: a repo is a site project when it is an
ojardila, non-archived, non-fork repo without the `no-monitor` topic and it
either has the `website` topic or ships a Gateway API `HTTPRoute` (under
`manifests/`, dev overlays excluded) with a public hostname (not `*.int.*`,
not wildcard). Missing `monitor.yaml` / workflow are committed to the default
branch as ojardila, Telegram secrets are copied in, and a first run is
dispatched. Generated configs carry `revalidate: true` until reviewed.

Opt out: topic `no-monitor`. Opt in a site without an HTTPRoute: topic
`website` + repo homepage URL.
