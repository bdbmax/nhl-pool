import { NewspaperIcon, TrendingUpIcon, UsersIcon } from "lucide-react"

import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"
import { ItemGroup } from "@/components/ui/item"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PageHeader, UpdatedLine } from "@/components/pool/page-header"
import { PlayerRow } from "@/components/pool/player-row"
import { RankChart } from "@/components/pool/rank-chart"
import { StandingsTable } from "@/components/pool/standings-table"
import { fmt, MANAGERS, pct, PLAYERS, POOL } from "@/lib/pool"

export default function StandingsPage() {
  const favorite = [...MANAGERS].sort((a, b) => b.win_pct - a.win_pct)[0]
  const started = POOL.season_started
  const key = (p: { points: number; proj: number | null }) => (started ? p.points : p.proj ?? 0)
  const top = [...PLAYERS].sort((a, b) => key(b) - key(a) || (b.proj ?? 0) - (a.proj ?? 0)).slice(0, 5)
  return (
    <>
      <div className="flex flex-col gap-2">
        <PageHeader
          title="Classement"
          description="Pour chaque équipe, les 6 meilleurs attaquants, les 4 meilleurs défenseurs et le meilleur gardien comptent."
        />
        <UpdatedLine />
      </div>

      {started && POOL.headline.length > 0 && (
        <Card size="sm">
          <CardHeader>
            <CardTitle>{POOL.update === "evening" ? "Ce soir" : "La une du jour"}</CardTitle>
            <CardDescription>{POOL.update === "evening" ? "Depuis ce matin." : "Depuis la mise à jour d'hier."}</CardDescription>
            <CardAction><NewspaperIcon aria-hidden className="size-4 text-muted-foreground" /></CardAction>
          </CardHeader>
          <CardContent>
            <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm">
              {POOL.headline.map((line) => <li key={line}>{line}</li>)}
            </ul>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-3">
        <Card size="sm">
          <CardHeader>
            <CardDescription>Favori</CardDescription>
            <CardTitle className="truncate">{favorite.name}</CardTitle>
          </CardHeader>
          <CardFooter className="text-xs text-muted-foreground">odds de {pct(favorite.win_pct)} de gagner</CardFooter>
        </Card>
        <Card size="sm">
          <CardHeader>
            <CardDescription>Matchs joués</CardDescription>
            <CardTitle className="tabular-nums">{fmt(POOL.games_played, POOL.games_played % 1 ? 1 : 0)}</CardTitle>
          </CardHeader>
          <CardFooter className="text-xs text-muted-foreground">en moyenne, sur {POOL.season_games} par équipe de la LNH</CardFooter>
        </Card>
      </div>

      <Tabs defaultValue="today">
        {/* Quatre onglets : texte plus petit sur les écrans très étroits (320 px) pour qu'ils tiennent. */}
        <TabsList className="w-full max-[359px]:[&_[data-slot=tabs-trigger]]:px-1 max-[359px]:[&_[data-slot=tabs-trigger]]:text-xs">
          <TabsTrigger value="today">Aujourd&apos;hui</TabsTrigger>
          <TabsTrigger value="projected">Projection</TabsTrigger>
          <TabsTrigger value="odds">Odds</TabsTrigger>
          {started && POOL.pace && <TabsTrigger value="pace">Rythme</TabsTrigger>}
        </TabsList>
        <TabsContent value="today"><StandingsTable view="today" /></TabsContent>
        <TabsContent value="projected"><StandingsTable view="projected" /></TabsContent>
        <TabsContent value="odds"><StandingsTable view="odds" /></TabsContent>
        {started && POOL.pace && <TabsContent value="pace"><StandingsTable view="pace" /></TabsContent>}
      </Tabs>

      <Card>
        <CardHeader>
          <CardTitle>Au fil de la saison</CardTitle>
          <CardDescription>Le rang et les odds de gagner de chaque équipe, matin après matin.</CardDescription>
          <CardAction><TrendingUpIcon aria-hidden className="size-4 text-muted-foreground" /></CardAction>
        </CardHeader>
        <CardContent>
          {started && POOL.history.length > 1 ? (
            <RankChart />
          ) : (
            <Empty>
              <EmptyHeader>
                <EmptyMedia variant="icon"><TrendingUpIcon /></EmptyMedia>
                <EmptyTitle>Dès le premier match</EmptyTitle>
                <EmptyDescription>Un point s&apos;ajoute chaque matin une fois la saison commencée.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{started ? "Meilleurs pointeurs" : "Meilleures projections"}</CardTitle>
          <CardDescription>
            {started ? "Les joueurs repêchés qui ont le plus de points jusqu'ici." : "Les joueurs repêchés qui ont les plus hauts totaux projetés."}
          </CardDescription>
          <CardAction><UsersIcon aria-hidden className="size-4 text-muted-foreground" /></CardAction>
        </CardHeader>
        <CardContent>
          <ItemGroup>
            {top.map((p, i) => (
              <PlayerRow key={p.nhl_id} player={p} rank={i + 1} value={key(p)} valueLabel={started ? "pts" : "proj."} showManager />
            ))}
          </ItemGroup>
        </CardContent>
      </Card>
    </>
  )
}
