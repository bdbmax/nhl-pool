import Link from "next/link"

import { Item, ItemActions, ItemContent, ItemDescription, ItemGroup, ItemMedia, ItemTitle } from "@/components/ui/item"
import { TeamAvatar, TeamCode } from "@/components/pool/team-avatar"
import { fmt, MANAGERS, POOL } from "@/lib/pool"

// Matchs restants cette semaine (lundi au dimanche) pour les 11 joueurs qui comptent de chaque équipe,
// sans les blessés et les absents. Plus de matchs, plus de chances de remonter.
export function WeekGames() {
  const week = POOL.week
  if (!week) return null
  const rows = [...MANAGERS]
    .map((m) => ({ m, ...(week.managers[String(m.id)] ?? { left: 0, total: 0 }) }))
    .sort((a, b) => b.left - a.left || b.total - a.total || a.m.rank - b.m.rank)
  const most = rows[0]?.left || 1
  return (
    <ItemGroup>
      {rows.map(({ m, left, total }) => (
        <Item key={m.id} size="sm" render={<Link href={`/teams/${m.id}`} />}>
          <ItemMedia><TeamAvatar id={m.id} name={m.name} size="sm" /></ItemMedia>
          <ItemContent className="min-w-0">
            <ItemTitle className="truncate">{m.name}<TeamCode id={m.id} /></ItemTitle>
            <ItemDescription>
              <span className="block h-1.5 rounded-full bg-muted" aria-hidden>
                <span className="block h-full rounded-full bg-foreground/70" style={{ width: `${(left / most) * 100}%` }} />
              </span>
            </ItemDescription>
          </ItemContent>
          <ItemActions>
            <span className="text-right text-sm tabular-nums">
              {fmt(left)}
              <span className="block text-xs text-muted-foreground">sur {fmt(total)}</span>
            </span>
          </ItemActions>
        </Item>
      ))}
    </ItemGroup>
  )
}
