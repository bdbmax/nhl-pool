# NHL pool 2026-27: projections and draft board

Draft-and-hold, best-ball pool. Each team drafts 8 F, 6 D and 2 G. The best 6 F, best 4 D and best 1 G
(season totals) count. Scoring: F goal 1, assist 1, GWG +1, hat trick +1. D goal 2, assist 1, GWG +1.
G win 2, OT/SO loss 1, shutout +3, goal 10.

Outputs:

- `output/board.html`: the draft board. A single file that works offline, so AirDrop or email it to your phone.
- `output/draft_list.csv`: the ranked list with projections, value over replacement, 80% ranges and flags.
- `output/backtest_report.md`: how the model did against the baseline on past seasons.

## Before the draft

1. Set `my_pick` and `draft_format` in `config/league.yaml`. The league is 13 teams; pick 6 and snake order are placeholders.
   You can also change them on the board's Settings tab without rerunning anything.
2. Review `data/manual/goalie_depth.csv` and fix any start share you disagree with. This is the single most
   important manual input (see below).
3. Refresh current-season sources and rebuild:

```
uv run python run.py project --refresh
uv run python run.py board
```

Do this again the day before the draft, since Daily Faceoff lines and injuries change through camp.

## Pool website: daily update

The site (`site/`, Next.js static export) is published to GitHub Pages at https://nhlpool.ca (domain on Cloudflare, DNS only; the old
https://bdbmax.github.io/nhl-pool/ redirects there).
`.github/workflows/daily.yml` runs every morning at 5:30 (Toronto) and can be started by hand
(Actions tab, "Daily update", "Run workflow"):

```
uv run python -m nhlpool.daily                 # real points, updated projections, odds -> site/data/pool.json
                                               # and data/history/<date>.json (standings, odds, player points)
uv run python -m nhlpool.daily --no-refresh    # same with cached downloads (quick local check)
uv run python -m nhlpool.daily --season 20252026 --as-of 2026-01-15 --out /tmp/replay   # replay last season
cd site && npm run dev                         # look at it locally
```

The daily job uses external projections only (ESPN, NHL.com, CBS, HockeyBangers), never our model:

- Real points: NHL stats API, games up to yesterday, league scoring.
- Rest of season: each source becomes per-game rates, updated with the player's real rate,
  `(40 x source + GP x real) / (40 + GP)`. Games left = his team's games left x the source's availability,
  minus absences (IR 10, Out 3, Day-to-day 1, Suspended 3). Goalie start shares are updated the same way
  (weight 20 team games). The weights live under `daily:` in `config/league.yaml`.
- Odds: 20,000 seasons; real points are fixed, the rest of the season varies, and the season-to-season
  surprise shrinks with the square root of the share of the season left.
- Weekly awards are recomputed from `data/history` every Monday; season awards (Joueur, Pick, Déception,
  Malchance de l'année, Roi de la montagne, Montagnes russes) every morning.
- Same-day updates every half hour from 12:05 to 1:35 (`--evening`) add the day's finished games and refresh
  injuries, trades and projections, on the site only; games still in progress never count, and the 5:30 run
  stays the official record in `data/history`. The Cloudflare Worker in `trigger/` starts them (and the 5:35
  morning run) on time; GitHub's own schedule in `daily.yml` is the backup.
- The home page shows arrows (places and odds gained since the previous update), "La une du jour" (a few
  lines generated from the numbers) and "Cette semaine" (games left this week for each team's counted players).
- Safety checks (192 players with three IDs, 12 teams of 16, no negative stats, no team losing more than
  2 real points overnight, skater goals and goalie wins reconcile with the scoreboard). If one fails, nothing
  is published, the site keeps yesterday's version and GitHub emails the failure.
- If the 5:30 update fails, it is retried at 6:30 and 7:30 (only if that morning's history file is not saved;
  see `scripts/gate.py`). The history is committed only after the site is published.
- A download that fails falls back to the previous copy (cached between runs). A drafted player whom no
  source projects keeps yesterday's pace. Draft IDs (NHL, ESPN, Daily Faceoff) are pinned in
  `data/pool_2026/draft_ids.csv`, so a player dropping off a lineup page keeps his IDs.
- Dress rehearsal: `uv run python scripts/rehearse.py --out /tmp/rehearsal` runs 14 seeded mornings (last
  season's opening fortnight shifted to this season's dates), with sites failing on purpose, and checks
  every output. The same runs on GitHub from the Actions tab ("Rehearsal").

## Rerun everything from scratch

```
uv sync                                   # Python env (pandas, numpy, scipy, scikit-learn)
uv run python run.py fetch                # download and cache 2010-11 to 2025-26 (about 10 minutes, idempotent)
uv run python run.py build                # processed tables and reconciliation checks
uv run python scripts/tune_b1.py          # optional: re-tune on tuning seasons -> config/params_b1.json
uv run python run.py backtest --validate  # report, including the held-out seasons
uv run python run.py project && uv run python run.py board
uv run pytest -q                          # scoring, draft logic, and no-leakage tests
```

Raw downloads are cached under `data/raw/` and reused. Historical files are never re-downloaded.
`--refresh` re-downloads only current-season sources: rosters, Daily Faceoff, ESPN and NHL.com.

## Data sources (all free, verified 2026-09-26)

| Source | Used for |
|---|---|
| NHL stats API (`api.nhle.com/stats/rest`) | Skater, goalie and team season stats since 2010-11, including GWG, TOI splits, primary assists and hat-trick games |
| NHL web API (`api-web.nhle.com`) | 2026-27 rosters, and player career lines in other leagues for rookies and imports |
| MoneyPuck season CSVs | Individual expected goals and goalie expected goals against |
| Daily Faceoff line combinations | Projected lines, PP1, starting goalie, injured reserve (current only, not archived) |
| ESPN fantasy API (public) | 2026-27 goal, assist and goalie projections, blended at 25% |
| NHL.com projections article | 2026-27 point projections, blended at 25% |
| gambling911 (BetOnline opening lines) | 2026-27 team point totals |

Natural Stat Trick, PuckPedia, CapWages and EliteProspects block scripted access, so they are not used.

## The model

Each category is projected as games played times a per-game rate.

- **Skater rates:** even-strength and power-play scoring are projected separately, as points per minute
  (weighted last three seasons, 2/1/1, lightly shrunk) times next season's minutes (last season, with 20% on
  the last six weeks). Goals are blended 25% toward expected goals.
  The age curve is fitted from the data: +8% a year under 22, +6% from 22 to 25, +1% from 25 to 30, −2% from
  30 to 33 and −5% after 33.
- **Game-winning goals:** team projected wins times the player's share of team goals, where team goals are
  built from the opening roster's projections. This beat each player's own GWG history.
- **Hat tricks:** Poisson probability of 3 or more goals from the goal rate, times 1.16 to correct for
  overdispersion measured on past seasons.
- **Games played:** last season's games-played fraction shrunk toward a prior. It rises for better scorers
  and falls slightly each year past 30.
- **Goalies:** start share times per-start W, OTL and SO rates. Start share is last season's share with a 25%
  weight on the team's last 20 games, so a goalie who took the job late gets credit. Win rate is half his own
  record and half team strength plus his goals saved above expected. Shutouts come from team shots against and
  his regressed save percentage. Each team's shares are capped at 100%.
- **Team strength:** 75% betting-market point totals and 25% regressed prior goal differential.
- **Rookies and imports:** prior-league scoring translated with league factors fitted on our own data, for
  example AHL 0.46, KHL 0.64, SHL 0.54 and NCAA 0.33. The shrinkage was calibrated on every past rookie
  season (208 players): projections are now about 4% low instead of 16%. Games played comes from the Daily
  Faceoff lineup.
- **Value:** projection minus replacement level, where replacement is the first undrafted player at each
  position (8 F, 6 D, 2 G per team). Alternatives such as counting only the scoring slots were backtested and
  did not reliably beat it with 13 teams. The board recomputes replacement after every pick.
- **80% ranges:** a Monte Carlo that resamples the model's own errors on the tuning seasons. On the
  held-out seasons, actual totals fell inside the range 81% of the time for forwards, 80% for defense and
  79% for goalies (79%, 79% and 76% on the 2013-14 to 2017-18 seasons).

Parameters were tuned only on 2018-19, 2019-20, 2021-22, 2022-23 and 2023-24. The 2013-14 to 2017-18
seasons were never used to choose anything until the round 4 overfitting check. The 2024-25 and 2025-26
seasons were never tuned on, but have been looked at after each round. See `output/backtest_report.md`.

### Rounds 2 and 3 (2026-09-27)

Twenty ideas were tested with standard errors and four opponent types. Five were kept: late-season goalie
start share, shutouts from shots and save percentage, goalie win rate mixed with team strength, team goals
from the opening roster, and taking your second goalie in your last two picks. The rookie shrinkage was also
recalibrated. Round 3 turned on the even-strength and power-play split, since the league drafts from public
rankings, and replaced the age curve with a flexible one. On the held-out seasons the gains are small. Every experiment, with its
numbers and decision, is in `output/experiments_round2.md`. Rerun them with `scripts/exp_part_a.py`,
`exp_part_b.py`, `exp_part_cd.py`, `exp_part_e.py` and `exp_rookies.py`.

### Round 4 (2026-09-27): overfitting audit

Every round was scored on five seasons it had never seen (2013-14 to 2017-18), with no retuning. Rounds 2
and 3 held up there. Round 1's games-played and ranking gains held up, but its skater-rate and goalie tuning
mostly did not. Each adopted piece was then switched off one at a time, and the main tuned numbers were
re-tuned leaving one season out. Four settings were a tie on the old seasons. A season-by-season check showed
three of them help in recent seasons: starters play fewer games now (about 60% of starts vs 66% in 2013-18),
and late-season minutes help in both eras. Those three were kept, since the draft is about 2026-27. Only the
extra weight on primary assists was removed. Six new
ideas (league scoring level, team expected goals, shots times shooting percentage, longer injury history, team
power-play time, scarcity-aware picks) had to pass a stricter bar: 2 standard errors on the tuning seasons
and no loss on the unseen ones. None did. Details in `output/experiments_round2.md` (round 4). Rerun with
`scripts/exp_round4_audit.py` and `scripts/exp_round4_ideas.py`. This is the final model for the 2026-27 draft.

### Tested and rejected

- **Best-ball-aware pick strategy:** each pick chose the largest simulated gain in the counted total. It lost
  about 48 points per season against opponents drafting by the model's value.
- **Ridge regression on rate features:** worse alone. A 50/50 blend with the Marcel model had slightly lower
  error but drafted worse, so it was not adopted.
- **Goalie wins from team goal differential instead of own history:** worse. Mixing half and half with the
  goalie's own quality won in round 2.
- **Teammates:** a player's opening-night teammates vs last season's teammates did not help. Actual season
  linemates would cut error by about 4%, but they are only known after the fact, so there is no usable
  preseason version. See `output/experiments_round2.md` (round 3).
- **Gradient boosting, start-share regression, upside picks, goalie timing rules, age-dependent weights,
  defense age curve, playoffs, draft pedigree, hits and size:** see `output/experiments_round2.md`.

## Manual inputs and judgment calls

These cannot be backtested because no historical archive exists. Each is a setting you can change.

| Input | Where | Default |
|---|---|---|
| Goalie start shares | `data/manual/goalie_depth.csv`, `start_share` column | Half model, half Daily Faceoff role (starter 62%, backup 30%) |
| Team point totals | `data/manual/team_point_totals.csv` | Opening betting lines |
| Weight on market vs goal differential | `market_weight` in league.yaml | 0.75 |
| Weight on public projections | `public_blend_weight` / `rookie_public_weight` | 0.25 / 0.5 |
| Games removed for injured reserve at camp | `ir_games_lost` | 10 |
| Per-player games-played override or exclusion | `data/manual/overrides.csv` (`playerId, name, proj_GP, exclude, note`) | Empty |
| Players missing from NHL roster lists but with a current team (unsigned or long-term injured) | Added automatically with an "off roster" flag | Check each one |
| Goalie win rate after a team change | Automatic: scaled by the new team's strength over the old team's last-season win rate, within 25% | On |

To reseed the goalie depth chart from fresh Daily Faceoff data, delete `data/manual/goalie_depth.csv`
and run `run.py project` twice. The first run writes the file and the second run applies it.

## Using the board

- The **?** button opens a guide to every number, bar, box and tag. It shows on first open until you hide it.
- Under each name: **ESPN #132 · model #15** is where ESPN ranks him (its draft room order, which autodraft
  follows) and where the model does. Green means ESPN has him at least two rounds later, so he can probably
  wait. Orange means ESPN has him at least two rounds earlier, so expect him to go sooner than the model says.
- The big number is projected season points. The plus number under it is points above replacement, and the
  list is sorted by it.
- **Mine** puts a player on your team and **Taken** gives him to someone else. **Undo** reverses the last pick.
- The red line at the top shows the current round, with your picks as yellow dots.
- **Need** shows only positions you still have to fill, and each position box shows how much its best
  available player is expected to fall before your next pick.
- A red left edge means the player is gone before your next pick in more than half of 200 simulated drafts.
  The draft is on ESPN, so in the simulation the other managers draft in ESPN's rank order (what the ESPN
  draft room lists and its autodraft follows) with random disagreement, while filling 8 F, 6 D and 2 G.
  Players ESPN does not rank come after, by public projections. How random is a setting ("How closely your
  league follows ESPN's rankings"). Each player's ESPN rank is shown when you tap him.
- Tap a player to see his chance of still being there at each of your picks, and the last pick where he is
  still there 8 times out of 10. "Watch this player" keeps that summary at the top of the board.
- Favorite team: Montreal players get +10 points of value for sorting, so they win close calls. Their
  projected points are unchanged. Team and bonus are in Settings and in `config/league.yaml`.
- Watched players get automatic warnings in a banner at the top. Blue means plan to take him at your next
  pick, yellow means he could go before your next pick, and red means take him now. Jakub Dobeš is watched
  by default (`watch` in `config/league.yaml`).
- Second goalie: once you have one goalie, the Need view hides goalies until your last two picks, because
  only your best goalie counts. This was the one pick-strategy rule that won in the backtest. Change it in
  Settings or with `second_goalie_last` in `config/league.yaml`.
- **My team** shows your projected counted total. Highlighted players are the ones currently counting.

## Draft night: saving and crash recovery

Draft on the computer with:

```
caffeinate -i uv run python run.py serve
```

It opens the board in your browser at `http://localhost:8000`. Leave the Terminal window open until the draft
is over, then press Ctrl+C. `caffeinate -i` keeps the Mac awake.

- **Where saves go.** Every pick is saved right away in the browser's database and in `data/drafts.sqlite`,
  with a restore point for every save. The line next to the draft name says where the last save went.
- **After a crash.** Run the command again and the board continues where you were. If the browser lost its
  data, the board restores the latest draft from the drafts file and says so.
- **Several drafts.** "+ New" starts a new draft, for example a mock draft. Click the draft name at the top to see
  every draft, open an older one, rename or delete one.
- **Going back in time.** The same window lists earlier moments of the open draft. "Go back here" returns to
  one, for example after a wrong click. These come from the drafts file too, so they survive a crash.
- **Backup file.** Settings can download every draft to a file and load it again.
- **Only this computer can connect.** Nobody else on the Wi-Fi can reach the board. To use a phone as well,
  run `uv run python run.py serve --phone`. That mode has no password, so stop it after the draft.

