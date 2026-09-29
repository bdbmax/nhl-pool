import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Item, ItemActions, ItemContent, ItemGroup, ItemMedia, ItemTitle } from "@/components/ui/item"
import { Progress } from "@/components/ui/progress"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PageHeader } from "@/components/pool/page-header"
import { PlayerRow } from "@/components/pool/player-row"
import { dayLabel, type FormRow, fmt, playerById, PLAYERS, POOL } from "@/lib/pool"

// En feu / À froid : les 7 derniers jours, points réels contre ce que la projection attendait pour les matchs joués.
function FormList({ rows, empty }: { rows: FormRow[]; empty: string }) {
  if (!rows.length) return <p className="text-sm text-muted-foreground">{empty}</p>
  return (
    <ItemGroup>
      {rows.map((r) => {
        const p = playerById(r.nhl_id)
        return p ? (
          <PlayerRow key={r.nhl_id} player={p} showManager signed value={r.diff} valueLabel={`${fmt(r.expected, 1)} attendus`}
            detail={`${fmt(r.points)} pts en ${fmt(r.games)} m.`} />
        ) : null
      })}
    </ItemGroup>
  )
}

export default function PlayersPage() {
  const key = (p: { points: number; proj: number | null }) => (POOL.season_started ? p.points : p.proj ?? 0)
  const top = [...PLAYERS, ...POOL.forgotten].sort((a, b) => key(b) - key(a)).slice(0, 25)
  const injured = PLAYERS.filter((p) => p.injury).sort((a, b) => (b.proj ?? 0) - (a.proj ?? 0))
  const maxTeam = POOL.nhl_teams[0]?.count ?? 1
  const label = POOL.season_started ? "pts" : "proj."

  return (
    <>
      <PageHeader title="Players" description="Tous les joueurs de la ligue, comptés selon les règles du pool." />
      <Tabs defaultValue="top">
        <TabsList className="w-full max-[389px]:[&_[data-slot=tabs-trigger]]:px-1 max-[389px]:[&_[data-slot=tabs-trigger]]:text-xs">
          <TabsTrigger value="top">Top</TabsTrigger>
          <TabsTrigger value="form">Forme</TabsTrigger>
          <TabsTrigger value="forgotten">Forgotten</TabsTrigger>
          <TabsTrigger value="nhl">NHL teams</TabsTrigger>
          <TabsTrigger value="injuries">Injuries</TabsTrigger>
        </TabsList>

        <TabsContent value="top">
          <Card>
            <CardHeader>
              <CardTitle>Meilleurs joueurs</CardTitle>
              <CardDescription>{POOL.season_started ? "Le plus de points du pool jusqu'ici" : "Les plus hauts totaux projetés"}, repêchés ou non.</CardDescription>
            </CardHeader>
            <CardContent>
              <ItemGroup>
                {top.map((p, i) => (
                  <PlayerRow key={p.nhl_id} player={p} rank={i + 1} value={key(p)} valueLabel={label} showManager detail={p.manager_id ? undefined : "non repêché"} />
                ))}
              </ItemGroup>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="form" className="flex flex-col gap-3">
          {POOL.hot_cold ? (
            <>
              <Card>
                <CardHeader>
                  <CardTitle>En feu</CardTitle>
                  <CardDescription>
                    Du {dayLabel(POOL.hot_cold.from)} au {dayLabel(POOL.hot_cold.to)} : les joueurs repêchés qui produisent le plus au-dessus
                    de leur projection pour les matchs qu&apos;ils ont joués (m.). À droite : l&apos;écart, et les points que la projection
                    attendait.
                  </CardDescription>
                </CardHeader>
                <CardContent><FormList rows={POOL.hot_cold.hot} empty="Personne au-dessus de sa projection pour l'instant." /></CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>À froid</CardTitle>
                  <CardDescription>Ceux qui produisent le plus en dessous de leur projection, sur la même période.</CardDescription>
                </CardHeader>
                <CardContent><FormList rows={POOL.hot_cold.cold} empty="Personne sous sa projection pour l'instant." /></CardContent>
              </Card>
            </>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>En feu et à froid</CardTitle>
                <CardDescription>
                  Dès que les joueurs auront joué quelques matchs : qui produit au-dessus ou en dessous de sa projection sur 7 jours.
                </CardDescription>
              </CardHeader>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="forgotten">
          <Card>
            <CardHeader>
              <CardTitle>Les oubliés</CardTitle>
              <CardDescription>Les meilleurs joueurs que personne n'a repêchés.</CardDescription>
            </CardHeader>
            <CardContent>
              <ItemGroup>
                {POOL.forgotten.map((p, i) => (
                  <PlayerRow key={p.nhl_id} player={p} rank={i + 1} value={key(p)} valueLabel={label} />
                ))}
              </ItemGroup>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="nhl">
          <Card>
            <CardHeader>
              <CardTitle>Équipes de la LNH les plus repêchées</CardTitle>
              <CardDescription>Nombre de joueurs repêchés dans chaque équipe de la LNH.</CardDescription>
            </CardHeader>
            <CardContent>
              <ItemGroup>
                {POOL.nhl_teams.map((t) => (
                  <Item key={t.team} size="sm">
                    <ItemMedia className="w-10 justify-start text-sm font-medium">{t.team}</ItemMedia>
                    <ItemContent><Progress value={(t.count / maxTeam) * 100} aria-label={`${t.team} : ${t.count} joueurs`} /></ItemContent>
                    <ItemActions><span className="w-6 text-right text-sm tabular-nums">{t.count}</span></ItemActions>
                  </Item>
                ))}
              </ItemGroup>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="injuries">
          <Card>
            <CardHeader>
              <CardTitle>Blessures</CardTitle>
              <CardDescription>Joueurs repêchés blessés, absents ou incertains, selon ESPN ou Daily Faceoff.</CardDescription>
            </CardHeader>
            <CardContent>
              <ItemGroup>
                {injured.map((p) => (
                  <PlayerRow key={p.nhl_id} player={p} value={p.proj} valueLabel="proj." showManager />
                ))}
              </ItemGroup>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </>
  )
}
