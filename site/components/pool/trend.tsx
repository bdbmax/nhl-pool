import { ChevronDownIcon, ChevronUpIcon } from "lucide-react"

import { fmt, POOL } from "@/lib/pool"

// Petite flèche sous une valeur : rangs gagnés (ou perdus) depuis la mise à jour précédente.
// Rien avant le premier match ni quand rien n'a bougé.
export function Trend({ change, unit = "rang" }: { change: number; unit?: "rang" | "pts" }) {
  if (!POOL.season_started || !POOL.compared_to || !change) return null
  const up = change > 0
  const n = Math.abs(change)
  const since = POOL.since || (POOL.update === "evening" ? "depuis ce matin" : "depuis hier")
  const label = unit === "rang"
    ? `${up ? "Monte" : "Descend"} de ${n} rang${n > 1 ? "s" : ""} ${since}`
    : `${up ? "Hausse" : "Baisse"} de ${fmt(n, 1)} point${n >= 2 ? "s" : ""} ${since}`
  const Icon = up ? ChevronUpIcon : ChevronDownIcon
  return (
    <span data-slot="trend" data-direction={up ? "up" : "down"} className="inline-flex items-center justify-end text-xs text-muted-foreground" aria-label={label} title={label}>
      <Icon aria-hidden className="size-3.5" />
      {unit === "rang" ? n : fmt(n, 1)}
    </span>
  )
}
