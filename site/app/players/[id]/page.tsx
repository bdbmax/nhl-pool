import Link from "next/link"
import { notFound } from "next/navigation"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table"
import { PlayerAvatar } from "@/components/pool/player-avatar"
import { PlayerWeeksChart } from "@/components/pool/player-weeks-chart"
import { TeamAvatar, TeamCode } from "@/components/pool/team-avatar"
import { fmt, injuryLabel, managerById, ord, playerById, PLAYERS, POOL, statLine, weeklyPoints } from "@/lib/pool"

// Une page par joueur (repêché ou oublié) : /players/<id NHL>/.
export function generateStaticParams() {
  return [...PLAYERS, ...POOL.forgotten].map((p) => ({ id: String(p.nhl_id) }))
}

const POS_LONG = { F: "Attaquant", D: "Défenseur", G: "Gardien" } as const

export default async function PlayerPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const p = playerById(Number(id))
  if (!p) notFound()
  const mgr = p.manager_id ? managerById(p.manager_id) : undefined
  const started = POOL.season_started
  const goalie = p.pos === "G"
  const injury = injuryLabel(p.injury)
  const realRate = p.gp ? p.points / p.gp : null
  const projRate = p.games_left ? (p.proj_left ?? 0) / p.games_left : null
  const weeks = weeklyPoints(p.nhl_id)
  const rows: [string, string][] = [
    ["Projection finale", `${fmt(p.proj)} pts`],
    ["D'ici la fin", `${fmt(p.proj_left)} pts`],
    [goalie ? "Départs restants" : "Matchs restants", fmt(p.games_left)],
    [goalie ? "Rythme projeté (par départ)" : "Rythme projeté", projRate == null ? "—" : `${fmt(projRate, 2)} pt par match`],
    ["Rythme réel", realRate == null ? "—" : `${fmt(realRate, 2)} pt par match`],
  ]

  return (
    <>
      <header className="flex items-center gap-4">
        <PlayerAvatar player={p} size="lg" className="size-20" />
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="text-2xl font-semibold tracking-tight break-words">{p.name}</h1>
          <p className="text-sm text-muted-foreground">
            {[p.number != null ? `#${p.number}` : null, p.nhl_team, POS_LONG[p.pos], p.age != null ? `${fmt(p.age, 0)} ans` : null]
              .filter(Boolean).join(" · ")}
          </p>
          {injury && <Badge variant="outline" className="w-fit">{injury}</Badge>}
        </div>
      </header>

      {mgr ? (
        <Link href={`/teams/${mgr.id}`} className="flex items-center gap-3 text-sm">
          <TeamAvatar id={mgr.id} name={mgr.name} size="sm" />
          <span>
            Repêché par <span className="font-medium">{mgr.name}</span><TeamCode id={mgr.id} />, {ord(p.round ?? 0, true)} ronde
            ({ord(p.overall ?? 0)} au total){started ? (p.counts ? ", compte pour son équipe" : ", au banc de son équipe") : ""}.
          </span>
        </Link>
      ) : (
        <p className="text-sm text-muted-foreground">Personne ne l&apos;a repêché.</p>
      )}

      <div className="grid grid-cols-3 gap-3">
        {([
          ["Points", fmt(p.points)],
          [goalie ? "Matchs" : "Matchs joués", fmt(p.gp)],
          ["Pts par match", realRate == null ? "—" : fmt(realRate, 2)],
        ] as const).map(([label, value]) => (
          <Card key={label} size="sm">
            <CardHeader>
              <CardDescription>{label}</CardDescription>
              <CardTitle className="tabular-nums">{value}</CardTitle>
            </CardHeader>
          </Card>
        ))}
      </div>
      {started && <p className="text-sm text-muted-foreground">Cette saison : {statLine(p)}.</p>}

      {started && weeks.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Semaine par semaine</CardTitle>
            <CardDescription>Ses points du pool chaque semaine, de lundi à lundi.</CardDescription>
          </CardHeader>
          <CardContent><PlayerWeeksChart id={p.nhl_id} /></CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Projection</CardTitle>
          <CardDescription>
            {started ? "Ses vrais points, plus la projection des matchs qui lui restent." : "La moyenne des quatre sources pour la saison."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table className="max-[359px]:text-xs max-[359px]:[&_td]:px-1 max-[359px]:[&_th]:px-1">
            <TableBody>
              {rows.map(([k, v]) => (
                <TableRow key={k}>
                  <TableCell className="whitespace-normal text-muted-foreground">{k}</TableCell>
                  <TableCell className="text-right tabular-nums">{v}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Selon chaque source</CardTitle>
          <CardDescription>Sa projection finale selon chacune des sources, avec ses vrais points déjà comptés.</CardDescription>
        </CardHeader>
        <CardContent>
          <Table className="max-[359px]:text-xs max-[359px]:[&_td]:px-1 max-[359px]:[&_th]:px-1">
            <TableBody>
              {POOL.projection_sources.map((s) => (
                <TableRow key={s}>
                  <TableCell className="whitespace-normal text-muted-foreground">{s}</TableCell>
                  <TableCell className="text-right tabular-nums">{p.sources[s] == null ? "ne le projette pas" : `${fmt(p.sources[s])} pts`}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </>
  )
}
