import Link from "next/link"

import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { InfoDrawer } from "@/components/pool/info-drawer"
import { TeamAvatar, TeamCode } from "@/components/pool/team-avatar"
import { fmt, MANAGERS, ord, pct, type Manager } from "@/lib/pool"

const VIEWS = {
  today: { label: "Points", value: (m: Manager) => fmt(m.points), sort: (m: Manager) => m.rank },
  projected: { label: "Pts projetés", value: (m: Manager) => fmt(m.expected_total), sort: (m: Manager) => -m.expected_total },
  odds: { label: "Odds", value: (m: Manager) => pct(m.win_pct), sort: (m: Manager) => -m.win_pct },
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
                  <span className="text-xs text-muted-foreground"><TeamCode id={m.id} />{ord(m.slot)} pick</span>
                </div>
              </Link>
            </TableCell>
            <TableCell className="text-right tabular-nums">{v.value(m)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
