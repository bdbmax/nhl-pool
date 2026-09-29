import Link from "next/link"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { InfoDrawer } from "@/components/pool/info-drawer"
import { TeamAvatar, TeamCode } from "@/components/pool/team-avatar"
import { Trend } from "@/components/pool/trend"
import { fmt, MANAGERS, ord, pct, POOL, type Manager } from "@/lib/pool"

const VIEWS = {
  today: { label: "Points", value: (m: Manager) => fmt(m.points), sort: (m: Manager) => m.rank },
  projected: { label: "Pts projetés", value: (m: Manager) => fmt(m.expected_total), sort: (m: Manager) => -m.expected_total },
  odds: { label: "Odds", value: (m: Manager) => pct(m.win_pct), sort: (m: Manager) => -m.win_pct },
}

// Sous le nom, dans l'onglet Aujourd'hui : matchs restants cette semaine (lundi au dimanche) pour les 11 joueurs
// qui comptent, sans les blessés. Ailleurs, le rang au draft.
function subline(view: keyof typeof VIEWS, m: Manager) {
  const w = view === "today" ? POOL.week?.managers[String(m.id)] : undefined
  if (!w) return `${ord(m.slot)} pick`
  return `${fmt(w.left)} match${w.left === 1 ? "" : "s"} cette sem.`
}

export function StandingsTable({ view }: { view: keyof typeof VIEWS }) {
  const v = VIEWS[view]
  const rows = [...MANAGERS].sort((a, b) => v.sort(a) - v.sort(b))
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-8">#</TableHead>
          <TableHead>Équipe</TableHead>
          <TableHead className="text-right">
            <span className="inline-flex items-center justify-end gap-0.5">
              {v.label}
              <InfoDrawer topic={view} />
            </span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((m, i) => (
          <TableRow key={m.id}>
            <TableCell className="tabular-nums text-muted-foreground">{i + 1}</TableCell>
            <TableCell>
              <Link href={`/teams/${m.id}`} className="flex items-center gap-3">
                <TeamAvatar id={m.id} name={m.name} size="sm" />
                <div className="flex min-w-0 flex-col">
                  <span className="truncate font-medium">{m.name}</span>
                  <span className="text-xs text-muted-foreground"><TeamCode id={m.id} />{subline(view, m)}</span>
                </div>
              </Link>
            </TableCell>
            <TableCell className="text-right tabular-nums">
              <div className="flex flex-col items-end">
                {v.value(m)}
                {view === "today" && <Trend change={m.rank_change} />}
                {view === "odds" && <Trend change={m.win_change} unit="pts" />}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
