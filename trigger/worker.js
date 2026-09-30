// Cloudflare Worker: starts the pool's daily update on GitHub at the right Toronto time.
// GitHub's own schedule (.github/workflows/daily.yml) is best effort and can start late or not at all;
// this timer is the reliable one, GitHub's schedule stays as a backup (an extra run is harmless).
//
// Cron trigger (UTC, set in the Cloudflare dashboard or wrangler.toml): "5,35 * * * *", every half hour.
// Cloudflare crons have no time zones either, so the Toronto time is worked out here:
//   05:35          morning update (official, writes the day's history)
//   22:05, 22:35, 23:05   evening updates (the day's finished games, site only)
// Secret GITHUB_TOKEN: a fine-grained token for bdbmax/nhl-pool only, permission "Actions: read and write".

const REPO = "bdbmax/nhl-pool"
const WORKFLOW = "daily.yml"
const SLOTS = { "05:35": "morning", "22:05": "evening", "22:35": "evening", "23:05": "evening" }

export function torontoTime(date) {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Toronto", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).format(date)
}

export function modeAt(date) {
  return SLOTS[torontoTime(date)] ?? null
}

async function dispatch(env, mode) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "nhlpool-trigger",
    },
    body: JSON.stringify({ ref: "main", inputs: { mode } }),
  })
  if (r.status !== 204) throw new Error(`GitHub answered ${r.status}: ${await r.text()}`)
}

export default {
  async scheduled(event, env) {
    const mode = modeAt(new Date(event.scheduledTime))
    if (mode) await dispatch(env, mode)
  },
}
