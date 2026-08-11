# DEPLOYMENT.md

# Masjid Events Perlis — Deployment Guide

The public site is a **static** website deployed to **GitHub Pages**. There is
no backend, no database, no login, and no build step on your laptop — GitHub
Actions builds the artifact, minifies it, checks performance budgets, and
publishes it.

## 1. How deployment works

The workflow `.github/workflows/deploy.yml` runs on every push to `main` (or
`master`) and on manual dispatch:

1. **Validate** canonical data (`tools/validate_data.py`) — invalid data
   aborts the whole deployment.
2. **Sync** `data/*.json` into the artifact's `public/data/`.
3. **Configure Pages** (`actions/configure-pages`) for the base URL.
4. **Generate PWA icons** (`tools/gen_icons.py`).
5. **Build static pages** (`tools/build_site.py`): no-JS SEO copies of every
   event/masjid page, `sitemap.xml`, `robots.txt`, and the stamped service
   worker `sw.js`, plus canonical/OpenGraph tags.
6. **Minify** `public/js` + `public/css` (comments/whitespace only).
7. **Perf gate** (`tools/perf_report.py`) — the artifact must stay within
   budgets or the deploy fails.
8. **Upload** `public/` as the Pages artifact and **deploy**.

Precisely `public/` is uploaded — the admin tool, tools, and `data/` never
reach the live site (`SECURITY.md`).

## 2. First-time setup on a repository

1. Push this repository to GitHub (e.g. `github.com/<you>/masjidperlis`).
2. Repository **Settings → Pages → Build and deployment → Source: GitHub
   Actions** (not "Deploy from a branch").
3. Confirm the **Actions** workflow tab shows a successful
   **Deploy to GitHub Pages** run after the push.
4. The site URL is shown in Settings → Pages. Project sites get
   `https://<user>.github.io/<repo>/`; user/org sites
   `https://<user>.github.io/`. Under a sub-path, every relative asset and the
   base-relative canonicals/sitemap still resolve correctly (the build uses
   relative paths when no `site_url` is configured).

## 3. Custom domain / https

- Add your domain under **Settings → Pages**, and the required `CNAME`
  (or apex A/AAAA records) at your DNS provider.
- HTTPS is automatic on GitHub Pages.
- If the site sits under a sub-path, the generated pages already use
  root-relative `../../` paths, so nothing needs changing.

## 4. Local preview before pushing

```bash
cp data/*.json public/data/          # refresh the mirror (or use Terbitkan)
python3 tools/build_site.py --site-url https://example.com --out /tmp/site
python3 -m http.server 8000 --directory /tmp/site
open http://localhost:8000
```

`build_site.py` validates first; broken data fails the build, matching CI.

## 5. Verifying a deployment

- **sitemap.xml** and **robots.txt** exist at the site root.
- Every event and masjid has a no-JS page at `event/<id>/` and
  `masjid/<id>/` (`event/<id>/event.ics` accompanies events).
- The event detail page has canonical + OpenGraph + JSON-LD (`@type: Event`).
- The service worker (`sw.js`) is stamped with the commit SHA; offline shell
  caching and network-first data keep cancellations fresh.
- Run `python3 tools/perf_report.py` against the fetched site to see the
  real payload.

## 6. CI checks (validate.yml)

Every push/PR runs: data validation, the full Python + Node test suites, the
accessibility audit, performance budgets, and `tools/security_audit.py`.
Anything failing blocks merge/deploy and is visible on the **Actions** tab.

## 7. Troubleshooting

| Symptom                        | Likely cause / fix                                             |
| ------------------------------ | ------------------------------------------------------------- |
| Pages not publishing           | Source must be **GitHub Actions** (not a branch) in Settings. |
| Deploy fails on validation     | `tools/validate_data.py` reports errors — fix `data/*.json`.  |
| Deploy fails on perf gate      | A page exceeded a budget — inspect `python3 tools/perf_report.py`. |
| Broken links on a custom domain| Check the `CNAME`/DNS and that pages use relative paths.      |
| Old cached data                | The service worker is network-first for data and stale-while-revalidate for shell; a fresh deploy stamps `CACHE_VERSION` so shell caches refresh automatically. |

## 8. How to go live with real content

1. Replace the sample `data/*.json` with real masjids/events (via the admin
   panel or a Google Sheet import, `ADMIN_GUIDE.md`).
2. Set `settings.json` → `site_url` to the final absolute base URL so
   canonicals and the sitemap are absolute.
3. `git push` and confirm the deployment. Then verify on a phone and in a
   no-JS browser: home, today/upcoming, search, filters, event + masjid
   details, share, `.ics`, maps, cancelled/recurring events.