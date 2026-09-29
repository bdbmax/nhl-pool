import { notFound } from "next/navigation"

import { Badge } from "@/components/ui/badge"
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Item, ItemActions, ItemContent, ItemDescription, ItemGroup, ItemMedia, ItemTitle } from "@/components/ui/item"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { InfoDrawer } from "@/components/pool/info-drawer"
import { PlayerAvatar } from "@/components/pool/player-avatar"
import { TeamOddsChart } from "@/components/pool/rank-chart"
import { TeamAvatar, TeamCode } from "@/components/pool/team-avatar"
import {
  countedProjection, fmt, injuryLabel, managerById, MANAGERS, ord, pct, POOL, POSITIONS, rosterOf, signed, statLine,
} from "@/lib/pool"
import { skaterStyle, standingsOrder } from "@/lib/jerseys"

export function generateStaticParams() {
  return MANAGERS.map((m) => ({ id: String(m.id) }))
}

export default async function TeamPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params
  const m = managerById(Number(id))
  if (!m) notFound()
  const roster = rosterOf(m.id)
  const started = POOL.season_started

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: skaterStyle(m.id, standingsOrder().find((o) => o.id !== m.id)!.id) }} />
      <header className="flex items-center gap-4">
        <TeamAvatar id={m.id} name={m.name} size="lg" />
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="truncate text-2xl font-semibold tracking-tight">{m.name}</h1>
          <p className="flex items-center gap-2 text-sm text-muted-foreground"><TeamCode id={m.id} />{ord(m.slot)} pick au draft</p>
        </div>
      </header>

      <div className="grid grid-cols-3 gap-3">
        {(started
          ? ([
              ["Rang", String(m.rank), "today"],
              ["Points", fmt(m.points), "today"],
              ["Odds", pct(m.win_pct), "odds"],
            ] as const)
          : ([
              ["Rang projeté", String(m.proj_rank), "projected"],
              ["Pts projetés", fmt(m.expected_total), "projected"],
              ["Odds", pct(m.win_pct), "odds"],
            ] as const)
        ).map(([label, value, topic]) => (
          <Card key={label} size="sm">
            <CardHeader>
              <CardDescription>{label}</CardDescription>
              <CardTitle className="tabular-nums">{value}</CardTitle>
              <CardAction><InfoDrawer topic={topic} /></CardAction>
            </CardHeader>
          </Card>
        ))}
      </div>

      {started && POOL.pace?.[String(m.id)] && (() => {
        const p = POOL.pace[String(m.id)]
        return (
          <p className="text-sm text-muted-foreground">
            Rythme : {p.ppg == null ? "aucun match joué" : `${fmt(p.ppg, 2)} pt par match joué`} pour les 11 joueurs qui comptent,
            {" "}et {fmt(p.left)} matchs à jouer d&apos;ici la fin de la saison
            {p.left_vs_avg ? ` (${signed(p.left_vs_avg)} par rapport à la moyenne des équipes)` : ", comme la moyenne des équipes"}.
          </p>
        )
      })()}

      {started && (
        <p className="text-sm text-muted-foreground">
          Projection finale : {fmt(m.expected_total)} points, {ord(m.proj_rank)} rang projeté. Pour chaque joueur :
          ses points jusqu&apos;ici, et sa projection finale en dessous.
        </p>
      )}

      <Tabs defaultValue="F">
        <TabsList className="w-full">
          {POSITIONS.map((c) => (
            <TabsTrigger key={c.pos} value={c.pos}>{c.label}</TabsTrigger>
          ))}
        </TabsList>
        {POSITIONS.map((c) => {
          const ps = roster.filter((p) => p.pos === c.pos).sort((a, b) => (b.proj ?? 0) - (a.proj ?? 0))
          const n = POOL.rules.counted[c.pos]
          return (
            <TabsContent key={c.pos} value={c.pos} className="flex flex-col gap-3">
              <p className="text-sm text-muted-foreground">
                {n === 1 ? "Le meilleur" : `Les ${n} meilleurs`} sur {POOL.rules.drafted[c.pos]}{" "}
                {n === 1 ? "compte" : "comptent"}, pour une projection de {fmt(countedProjection(m.id, c.pos))} points
                {started ? " d'ici la fin de la saison (vrais points compris)" : ""}. Les autres servent de réserve.
              </p>
              <ItemGroup>
                {ps.map((p) => {
                  const injury = injuryLabel(p.injury)
                  return (
                    <Item key={p.nhl_id} size="sm" variant={p.counts ? "outline" : "muted"}>
                      <ItemMedia><PlayerAvatar player={p} /></ItemMedia>
                      <ItemContent className="min-w-0">
                        <ItemTitle className="truncate">{p.name}</ItemTitle>
                        <ItemDescription className="truncate">
                          {started
                            ? `${p.nhl_team}, ${fmt(p.gp)} PJ, ${statLine(p)}`
                            : `${p.nhl_team}, ${ord(p.round ?? 0, true)} ronde, ${fmt(p.proj_gp)} PJ`}
                        </ItemDescription>
                      </ItemContent>
                      <ItemActions>
                        {injury && <Badge variant="outline">{injury}</Badge>}
                        <Badge variant={p.counts ? "default" : "secondary"}>{p.counts ? "Compte" : "Banc"}</Badge>
                        {started ? (
                          <span className="w-10 text-right text-sm tabular-nums">
                            {fmt(p.points)}
                            <span className="block text-xs text-muted-foreground">{fmt(p.proj)}</span>
                          </span>
                        ) : (
                          <span className="w-8 text-right text-sm tabular-nums">{fmt(p.proj)}</span>
                        )}
                      </ItemActions>
                    </Item>
                  )
                })}
              </ItemGroup>
            </TabsContent>
          )
        })}
      </Tabs>

      {started && POOL.history.length > 1 && (
        <Card>
          <CardHeader>
            <CardTitle>Odds au fil de la saison</CardTitle>
            <CardDescription>Ses odds de gagner le pool, matin après matin. Les autres équipes sont en gris.</CardDescription>
            <CardAction><InfoDrawer topic="odds" /></CardAction>
          </CardHeader>
          <CardContent><TeamOddsChart id={m.id} /></CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Odds pour chaque rang final</CardTitle>
          <CardDescription>Selon 20 000 saisons simulées.</CardDescription>
          <CardAction><InfoDrawer topic="odds" /></CardAction>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                {m.finish_odds.slice(0, 6).map((_, i) => <TableHead key={i} className="text-right">{ord(i + 1)}</TableHead>)}
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                {m.finish_odds.slice(0, 6).map((o, i) => <TableCell key={i} className="text-right tabular-nums">{pct(o, 0)}</TableCell>)}
              </TableRow>
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Bilan du draft</CardTitle>
          <CardDescription>
            Chaque pick, et {started ? "ses points" : "sa projection"} par rapport à la moyenne des picks de la même ronde.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ItemGroup>
            {roster.map((p) => (
              <Item key={p.nhl_id} size="sm">
                <ItemMedia className="w-16 justify-start text-xs tabular-nums text-muted-foreground">
                  {ord(p.round ?? 0, true)} ronde
                </ItemMedia>
                <ItemContent className="min-w-0"><ItemTitle className="truncate">{p.name}</ItemTitle></ItemContent>
                <ItemActions><span className="text-sm tabular-nums">{signed(p.vs_round)}</span></ItemActions>
              </Item>
            ))}
          </ItemGroup>
        </CardContent>
      </Card>
    </>
  )
}
