# Pool website

The pool website: greyscale, mobile-first, built only from shadcn/ui components (Next.js, Base UI,
Tailwind). It reads `data/pool.json`, written by the Python side:

```
cd ..
uv run python -m nhlpool.site_export --refresh   # --refresh re-reads current teams and headshots
```

Every player has three verified IDs: `nhl_id` (NHL APIs and MoneyPuck), `espn_id` (ESPN fantasy API) and
`df_id` (Daily Faceoff). Photos are the NHL's official headshots, keyed by `nhl_id`. HockeyDB was checked and
has no player photos. Before the season starts, points are 0 and rankings use projections.

Projections and odds use external sources only: ESPN, NHL.com, CBS and HockeyBangers
(`src/nhlpool/external.py`, odds in `scripts/rate_teams.py`). Our own draft model is not used on the site.
The site is light mode only. The header button (or the R key) switches between the Moderne and Rétro skins (`app/skins.css`).

```
npm install
npm run dev        # http://localhost:3000
npm run build      # static site in out/, ready for GitHub Pages or Cloudflare Pages
```

Pages:

- `/` standings: today, projected final and odds, ranking over time, hot this week
- `/teams` and `/teams/[id]`: each roster by position, which players count, injuries, points by week, draft recap
- `/draft`: steals, busts and the full 16-round board
- `/players`: top scorers, the forgotten (best undrafted), most-picked NHL teams, injuries
- `/awards`: weekly awards and a head-to-head comparison

Data types and helpers are in `lib/pool.ts`. The daily job will rewrite `data/pool.json` each morning.
