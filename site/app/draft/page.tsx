import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ItemGroup } from "@/components/ui/item"
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { PageHeader } from "@/components/pool/page-header"
import { PlayerRow } from "@/components/pool/player-row"
import { TeamAvatar, TeamCode } from "@/components/pool/team-avatar"
import { MANAGERS, ord, PLAYERS, POOL, POS_SHORT, ROUNDS } from "@/lib/pool"

export default function DraftPage() {
  const byValue = [...PLAYERS].sort((a, b) => (b.vs_round ?? 0) - (a.vs_round ?? 0))
  const steals = byValue.filter((p) => (p.round ?? 0) >= 4).slice(0, 10)
  const busts = [...byValue].reverse().filter((p) => (p.round ?? 99) <= 6).slice(0, 10)
  const slots = [...MANAGERS].sort((a, b) => a.slot - b.slot)
  const cell = new Map(PLAYERS.map((p) => [`${p.round}-${p.manager_id}`, p]))
  const basis = POOL.season_started ? "Points récoltés" : "Points projetés"

  return (
    <>
      <PageHeader title="Draft" description="Les 192 picks, et ce que chacun rapporte." />
      <Tabs defaultValue="steals">
        <TabsList className="w-full">
          <TabsTrigger value="steals">Steals</TabsTrigger>
          <TabsTrigger value="busts">Busts</TabsTrigger>
          <TabsTrigger value="board">Board</TabsTrigger>
        </TabsList>

        <TabsContent value="steals">
          <Card>
            <CardHeader>
              <CardTitle>Les meilleurs picks pour leur ronde</CardTitle>
              <CardDescription>{basis} au-dessus de la moyenne des picks de la même ronde, à partir de la 4e ronde.</CardDescription>
            </CardHeader>
            <CardContent>
              <ItemGroup>
                {steals.map((p, i) => (
                  <PlayerRow key={p.nhl_id} player={p} rank={i + 1} detail={`${ord(p.round ?? 0, true)} ronde`} value={p.vs_round} valueLabel="écart" showManager signed />
                ))}
              </ItemGroup>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="busts">
          <Card>
            <CardHeader>
              <CardTitle>Les picks qui pourraient décevoir</CardTitle>
              <CardDescription>{basis} les plus loin sous la moyenne de leur ronde, de la 1re à la 6e ronde.</CardDescription>
            </CardHeader>
            <CardContent>
              <ItemGroup>
                {busts.map((p, i) => (
                  <PlayerRow key={p.nhl_id} player={p} rank={i + 1} detail={`${ord(p.round ?? 0, true)} ronde`} value={p.vs_round} valueLabel="écart" showManager signed />
                ))}
              </ItemGroup>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="board">
          <ScrollArea className="w-full rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="sticky left-0 bg-background">Ronde</TableHead>
                  {slots.map((m) => (
                    <TableHead key={m.id} className="min-w-32">
                      <span className="flex items-center gap-2"><TeamAvatar id={m.id} name={m.name} size="sm" />{m.name}<TeamCode id={m.id} /></span>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {Array.from({ length: ROUNDS }, (_, r) => (
                  <TableRow key={r}>
                    <TableCell className="sticky left-0 bg-background tabular-nums text-muted-foreground">{r + 1}</TableCell>
                    {slots.map((m) => {
                      const p = cell.get(`${r + 1}-${m.id}`)
                      return (
                        <TableCell key={m.id}>
                          <div className="flex flex-col">
                            <span className="truncate">{p?.name ?? "—"}</span>
                            <span className="text-xs text-muted-foreground">{p ? `${POS_SHORT[p.pos]}, ${p.nhl_team}` : ""}</span>
                          </div>
                        </TableCell>
                      )
                    })}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <ScrollBar orientation="horizontal" />
          </ScrollArea>
        </TabsContent>
      </Tabs>
    </>
  )
}
