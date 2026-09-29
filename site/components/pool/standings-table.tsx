import Link from "next/link"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { InfoDrawer } from "@/components/pool/info-drawer"
import { TeamAvatar, TeamCode } from "@/components/pool/team-avatar"
import { Trend } from "@/components/pool/trend"
import { fmt, MANAGERS, ord, pct, POOL, signed, type Manager } from "@/lib/pool"

const VIEWS = {
  today: { label: "Points", value: (m: Manager) => fmt(m.points), sort: (m: Manager) => m.rank },
  projected: { label: "Pts projetés", value: (m: Manager) => fmt(m.expected_total), sort: (m: Manager) => -m.expected_total },
  odds: { label: "Odds", value: (m: Manager) => pct(m.win_pct), sort: (m: Manager) => -m.win_pct },
  pace: { label: "Pts par match", value: (m: Manager) => fmt(paceOf(m)?.ppg, 2), sort: (m: Manager) => -(paceOf(m)?.ppg ?? 0) },
}

function paceOf(m: Manager) {
  return POOL.pace?.[String(m.id)]
}

// Sous le nom. Aujourd'hui : matchs à jouer cette semaine sur le total de la semaine (lundi au dimanche), pour
// les 11 joueurs qui comptent, sans les blessés. Rythme : matchs à jouer d'ici la fin de la saison, et l'écart
// avec la moyenne des équipes. Ailleurs, le rang au draft.
function subline(view: keyof typeof VIEWS, m: Manager) {
  const w = view === "today" ? POOL.week?.managers[String(m.id)] : undefined
  const p = view === "pace" ? paceOf(m) : undefined
  if (w) return `${fmt(w.left)}/${fmt(w.total)} à jouer cette sem.`
  if (p) return `${fmt(p.left)} matchs à jouer (${p.left_vs_avg ? signed(p.left_vs_avg) : "moy."})`
  return `${ord(m.slot)} pick`
}

export function StandingsTable({ view }: { view: keyof typeof VIEWS }) {
  const v = VIEWS[view]
  const rows = [...MANAGERS].sort((a, b) => v.sort(a) - v.sort(b))
  return (
    // Fixed columns: rank, value, and the team taking the rest. With automatic widths the wide retro font let the
    // longest name or header push the table past a phone's screen; here a long name is cut short instead.
    <Table className="table-fixed">
      <TableHeader>
        <TableRow>
          <TableHead className="w-8">#</TableHead>
          {/* The "?" sits by "Équipe": next to the value label it made that column too wide for phones. */}
          <TableHead>
            <span className="inline-flex items-center gap-0.5">Équipe<InfoDrawer topic={view} /></span>
          </TableHead>
          <TableHead className="w-[4.5rem] text-right whitespace-normal leading-tight">{v.label}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((m, i) => (
          <TableRow key={m.id}>
            <TableCell className="tabular-nums text-muted-foreground">{i + 1}</TableCell>
            {/* whitespace-normal: a long line under the name wraps instead of widening the table past the screen. */}
            <TableCell className="whitespace-normal">
              <Link href={`/teams/${m.id}`} className="flex min-w-0 items-center gap-3">
                <TeamAvatar id={m.id} name={m.name} size="sm" />
                <div className="flex min-w-0 flex-col">
                  <span className="flex min-w-0 items-center"><span className="truncate font-medium">{m.name}</span><TeamCode id={m.id} /></span>
                  <span className="text-xs text-muted-foreground">{subline(view, m)}</span>
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
