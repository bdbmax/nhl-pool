import fs from "node:fs"
import path from "node:path"
import { MANAGERS, PLAYERS, POOL } from "@/lib/pool"

export type RecapPlayer = {
  id: number
  points: number
  games: number
  stats: Record<string, number> | null
}
export type TeamRecap = {
  id: number
  before: number
  points: number
  gain: number
  rank: number
  previousRank: number
  production: number
  players: RecapPlayer[]
}
export type Edition = {
  date: string
  from: string
  to: string
  teams: TeamRecap[]
}
type Snapshot = {
  date: string
  as_of: string
  managers: Record<string, { points: number; rank: number }>
  players: Record<string, [number, number, ...unknown[]]>
  stats?: Record<string, Record<string, number>>
}

// Official morning records only: afternoon refreshes never rewrite a daily edition.
export function dailyEditions(): Edition[] {
  const folder = path.join(process.cwd(), "..", "data", "history")
  if (!fs.existsSync(folder)) return []
  const snapshots: Snapshot[] = fs
    .readdirSync(folder)
    .filter((f) => /^\d{4}-\d{2}-\d{2}\.json$/.test(f))
    .sort()
    .map((f) => JSON.parse(fs.readFileSync(path.join(folder, f), "utf8")))
  return snapshots
    .slice(1)
    .flatMap((cur, i) => {
      const prev = snapshots[i]
      if (cur.as_of <= prev.as_of) return []
      const teams = MANAGERS.flatMap((m) => {
        const a = cur.managers[String(m.id)],
          b = prev.managers[String(m.id)]
        const roster = PLAYERS.filter((p) => p.manager_id === m.id)
        if (
          !a ||
          !b ||
          roster.some(
            (p) =>
              !cur.players[String(p.nhl_id)] || !prev.players[String(p.nhl_id)]
          )
        )
          return []
        const players = roster
          .map((p) => {
            const id = String(p.nhl_id),
              now = cur.players[id],
              old = prev.players[id]
            const ns = cur.stats?.[id],
              os = prev.stats?.[id]
            return {
              id: p.nhl_id,
              points: now[0] - old[0],
              games: now[1] - old[1],
              stats:
                ns && os
                  ? Object.fromEntries(
                      Object.entries(ns).map(([k, v]) => [k, v - (os[k] ?? 0)])
                    )
                  : null,
            }
          })
          .sort((a, b) => b.points - a.points || a.id - b.id)
        return [
          {
            id: m.id,
            before: b.points,
            points: a.points,
            gain: a.points - b.points,
            rank: a.rank,
            previousRank: b.rank,
            production: players.reduce((s, p) => s + p.points, 0),
            players,
          },
        ]
      })
      if (
        !teams.length ||
        !teams.some((t) => t.players.some((p) => p.games || p.points))
      )
        return []
      return [{ date: cur.date, from: prev.as_of, to: cur.as_of, teams }]
    })
    .filter((e) => e.to <= POOL.as_of)
    .reverse()
}
