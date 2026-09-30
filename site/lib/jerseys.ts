import data from "@/lib/jerseys.json"
import { MANAGERS, POOL } from "@/lib/pool"

// Habillage Rétro : un chandail pixel et un code de 3 lettres par équipe (lib/jerseys.json).
// Les images sont générées par scripts/make_jerseys.py dans public/skins/retro/jerseys/.
export type Jersey = { code: string; main: string; trim: string; stripe: string }

export function jerseyOf(id: number): Jersey {
  return (data as unknown as Record<string, Jersey>)[String(id)]
}

export const jerseyImage = (id: number, kind: "badge" | "up" | "down") => `url(${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/skins/retro/jerseys/${id}-${kind}.png)`

function luminance(hex: string) {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

// Text color for the code tag: the jersey's trim if it reads well on the main color, else ink or paper.
export function codeTextColor(j: Jersey) {
  return [j.trim, j.stripe, "#1c1b19", "#fffdf7"].find((c) => contrast(c, j.main) >= 4.5) ?? "#1c1b19"
}

// Current order: real points once the season starts, projections before.
export function standingsOrder() {
  return [...MANAGERS].sort((a, b) =>
    POOL.season_started ? b.points - a.points || b.expected_total - a.expected_total : b.expected_total - a.expected_total
  )
}

// Les deux joueurs en arrière-plan : celui qui monte porte le chandail de `up`, celui qui descend celui de `down`.
export function skaterStyle(up: number, down: number) {
  return `html[data-skin="retro"]{--skater-up:${jerseyImage(up, "up")};--skater-down:${jerseyImage(down, "down")}}`
}

// En Rétro, la couleur d'une équipe (--team-N, p. ex. sa ligne dans « Au fil de la saison ») est celle de son chandail.
// Un chandail blanc ne se verrait pas sur le papier : on prend alors sa bordure.
export function teamColorStyle() {
  const vars = MANAGERS.map((m) => {
    const j = jerseyOf(m.id)
    return `--team-${m.id}:${contrast(j.main, "#fffdf7") >= 1.5 ? j.main : j.trim}`
  })
  return `html[data-skin="retro"]{${vars.join(";")}}`
}
