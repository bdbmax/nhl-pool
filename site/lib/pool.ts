import pool from "@/data/pool.json"

// Data written every morning by `uv run python -m nhlpool.daily` (site/data/pool.json).
// Every player has three positive IDs: nhl_id (NHL APIs, MoneyPuck), espn_id (ESPN), df_id (Daily Faceoff).
export type Pos = "F" | "D" | "G"

export type Player = {
  nhl_id: number
  espn_id: number
  df_id: number
  slug: string
  name: string
  pos: Pos
  nhl_team: string
  number: number | null
  photo: string | null
  photo_fallback: string
  injury: string | null
  points: number
  gp: number
  stats: Partial<Record<string, number>>
  proj: number | null
  proj_left: number | null
  games_left: number | null
  proj_gp: number | null
  age: number | null
  sources: Record<string, number | null>
  manager_id?: number
  round?: number
  overall?: number
  counts?: boolean
  vs_round?: number | null
}

export type Manager = {
  id: number
  name: string
  slot: number
  rank: number
  proj_rank: number
  points: number
  proj_consensus: number
  expected_total: number
  expected_finish: number
  win_pct: number
  finish_odds: number[]
  rank_change: number // places gained since the previous update (negative: lost)
  win_change: number // win odds change, in percentage points
}

// Trophées de la semaine : un top 3 par trophée (daily.weekly_awards).
export type Award = {
  week_end: string
  from: string
  to: string
  pick: { nhl_id: number; manager_id: number; value: number; round: number }[]
  comeback: { manager_id: number; value: number; from: number; to: number }[]
  bad_luck: { manager_id: number; value: number; games: number }[]
  drought: { manager_id: number; value: number }[]
}

// Trophées de la saison, recalculés chaque matin (daily.season_awards) : un top 3 par trophée.
export type SeasonEntry = {
  manager_id: number
  value: number
  nhl_id?: number
  round?: number
  gap?: number
  points?: number
  mornings?: number
  worst?: { nhl_id: number; games: number } | null
  best?: { nhl_id: number; points: number }
}
export type SeasonAward = {
  key: "player" | "pick" | "bust" | "bad_luck" | "king" | "rollercoaster" | "bench"
  podium: SeasonEntry[]
}

export type TonightGame = { nhl_id: number; team: string; opp: string; home: boolean; start: string | null; counts: boolean }
export type RaceSide = { manager_id: number; gap: number; left_diff: number; ppg: number | null }
export type FormRow = { nhl_id: number; points: number; games: number; expected: number; diff: number }

type Pool = {
  season: string
  season_start: string
  as_of: string
  games_played: number
  season_games: number
  real_weight_games: number
  // One entry per morning (data/history): rank, real points and win odds (%) per manager id.
  history: { date: string; ranks: Record<string, number>; points: Record<string, number>; win: Record<string, number> }[]
  awards: Award[]
  // "morning": the official 5:30 update. "evening": a same-day update (every half hour, noon to 1:30).
  update: "morning" | "evening"
  // Since when the arrows count, in words: "depuis hier", "depuis ce matin", "depuis hier matin".
  since?: string
  compared_to: string | null
  headline: string[]
  week: { start: string; end: string; managers: Record<string, { left: number; total: number }> } | null
  season_awards: SeasonAward[]
  // Per manager, for his 11 counted players: points per game played, games played, NHL games left this season.
  pace: Record<string, { gp: number; points: number; ppg: number | null; left: number; left_vs_avg: number }> | null
  tonight: { date: string; managers: Record<string, TonightGame[]> } | null
  race: Record<string, { ahead: RaceSide | null; behind: RaceSide | null; catch_weeks: number | null; caught_weeks: number | null }> | null
  hot_cold: { from: string; to: string; hot: FormRow[]; cold: FormRow[] } | null
  player_weeks: { dates: string[]; points: Record<string, number[]> }
  projection_sources: string[]
  generated: string
  season_started: boolean
  rules: { counted: Record<Pos, number>; drafted: Record<Pos, number>; teams: number; rounds: number }
  managers: Manager[]
  players: Player[]
  forgotten: Player[]
  nhl_teams: { team: string; count: number }[]
}

export const POOL = pool as Pool
export const MANAGERS = POOL.managers
export const PLAYERS = POOL.players
export const ROUNDS = POOL.rules.rounds

export const POSITIONS = [
  { pos: "F", label: "Attaquants" },
  { pos: "D", label: "Défenseurs" },
  { pos: "G", label: "Gardiens" },
] as const

export const NAV = [
  { href: "/", label: "Classement", icon: "trophy" },
  { href: "/teams", label: "Équipes", icon: "users" },
  { href: "/draft", label: "Draft", icon: "list" },
  { href: "/players", label: "Players", icon: "star" },
  { href: "/awards", label: "Trophées", icon: "award" },
] as const

// Les points d'un joueur sont des points de pool, pas ceux de la LNH : un but vaut 2 pour un défenseur.
export const PTS = "pts pool"
export const SCORING: Record<Pos, string> = {
  F: "1 par but et par passe, 1 de plus par but gagnant et par tour du chapeau",
  D: "2 par but, 1 par passe, 1 de plus par but gagnant",
  G: "2 par victoire, 1 par défaite en prolongation ou en tirs de barrage, 3 de plus par blanchissage",
}

// Position abrégée à la québécoise : A (attaquant), D (défenseur), G (gardien).
export const POS_SHORT: Record<Pos, string> = { F: "A", D: "D", G: "G" }

const INJURY: Record<string, string> = {
  IR: "Blessé",
  Out: "Absent",
  "Day-to-day": "Incertain",
  Suspended: "Suspendu",
}
export const injuryLabel = (s: string | null) => (s ? INJURY[s] ?? s : null)

export function initials(name: string) {
  return name.replace(/[^A-Za-zÀ-ÿ .-]/g, "").split(/[ .-]+/).filter(Boolean).map((w) => w[0]).slice(0, 2).join("").toUpperCase()
}

export function managerById(id: number) {
  return MANAGERS.find((m) => m.id === id)
}

export function rosterOf(id: number) {
  return PLAYERS.filter((p) => p.manager_id === id).sort((a, b) => (a.overall ?? 0) - (b.overall ?? 0))
}

export function playerById(id: number) {
  return PLAYERS.find((p) => p.nhl_id === id) ?? POOL.forgotten.find((p) => p.nhl_id === id)
}

// Points du pool d'un joueur repêché, semaine par semaine (lundi à lundi), tirés de data/history.
export function weeklyPoints(id: number) {
  const { dates, points } = POOL.player_weeks
  const cum = points[String(id)]
  if (!cum || dates.length < 2) return []
  return dates.slice(1).map((d, i) => ({ from: dates[i], date: d, pts: cum[i + 1] - cum[i] }))
}

// Page d'un joueur : /players/<id NHL>/.
export const playerHref = (p: { nhl_id: number }) => `/players/${p.nhl_id}/`

// Heure d'un match, à Toronto : « 19 h », « 22 h 30 ».
export function gameTime(iso: string | null) {
  if (!iso) return ""
  return new Date(iso).toLocaleTimeString("fr-CA", { hour: "numeric", minute: "2-digit", timeZone: "America/Toronto" })
    .replace(/ h 00$/, " h")
}

// Total compté : 6 meilleurs attaquants, 4 défenseurs et 1 gardien, selon la projection finale
// (vrais points jusqu'ici + projection des matchs restants).
export function countedProjection(id: number, pos?: Pos) {
  return rosterOf(id).filter((p) => p.counts && (!pos || p.pos === pos)).reduce((s, p) => s + (p.proj ?? 0), 0)
}

// Nombres à la québécoise : virgule décimale, espace avant le %.
export const fmt = (x: number | null | undefined, d = 0) =>
  x == null ? "—" : x.toLocaleString("fr-CA", { minimumFractionDigits: d, maximumFractionDigits: d })
export const pct = (x: number | null | undefined, d = 1) => (x == null ? "—" : `${fmt(x, d)}\u00a0%`)
export const signed = (x: number | null | undefined, d = 0) => (x == null ? "—" : `${x > 0 ? "+" : ""}${fmt(x, d)}`)

export function updatedLabel() {
  return new Date(POOL.generated).toLocaleString("fr-CA", {
    day: "numeric", month: "long", hour: "numeric", minute: "2-digit", timeZone: "America/Toronto",
  })
}

export function listJoin(items: readonly string[]) {
  return items.length < 2 ? items.join("") : `${items.slice(0, -1).join(", ")} et ${items[items.length - 1]}`
}

// Ordinaux : 1er choix, 2e choix ; 1re ronde, 2e ronde.
export const ord = (n: number, feminine = false) => (n === 1 ? (feminine ? "1re" : "1er") : `${n}e`)

const FR_DAY = { day: "numeric", month: "long", timeZone: "UTC" } as const

export function dayLabel(iso: string) {
  return new Date(`${iso}T12:00:00Z`).toLocaleDateString("fr-CA", FR_DAY)
}

// Fiche du joueur : 12 B, 20 P ou 8 V, 2 BL.
export function statLine(p: Player) {
  const s = p.stats ?? {}
  return p.pos === "G" ? `${s.W ?? 0} V, ${s.OTL ?? 0} DP, ${s.SO ?? 0} BL` : `${s.G ?? 0} B, ${s.A ?? 0} P`
}

// Date du premier match de la saison, lue dans le calendrier de la LNH.
export function seasonStartLabel() {
  return new Date(`${POOL.season_start}T12:00:00Z`).toLocaleDateString("fr-CA", FR_DAY)
}
