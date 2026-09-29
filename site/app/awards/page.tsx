import { BandageIcon, CrownIcon, RocketIcon, SkullIcon } from "lucide-react"

import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Item, ItemContent, ItemDescription, ItemGroup, ItemTitle } from "@/components/ui/item"
import { PageHeader } from "@/components/pool/page-header"
import { HeadToHead } from "@/components/pool/head-to-head"
import { PlayerRow } from "@/components/pool/player-row"
import { TeamAvatar } from "@/components/pool/team-avatar"
import { type Award, dayLabel, firstAwardsLabel, fmt, managerById, ord, playerById, POOL, seasonStartLabel } from "@/lib/pool"

const AWARDS = [
  { key: "pick", title: "Pick de la semaine", description: "Le pick tardif (9e ronde ou plus loin) qui a récolté le plus de points cette semaine.", icon: CrownIcon },
  { key: "comeback", title: "Meilleure remontée", description: "L'équipe qui a gagné le plus de rangs cette semaine.", icon: RocketIcon },
  { key: "bad_luck", title: "Malchance", description: "Le plus de points projetés perdus à cause des blessures.", icon: BandageIcon },
  { key: "drought", title: "Disette", description: "Le moins de points au cours des 7 derniers jours.", icon: SkullIcon },
] as const

function Winner({ award, kind }: { award: Award; kind: (typeof AWARDS)[number]["key"] }) {
  if (kind === "pick") {
    const p = award.pick && playerById(award.pick.nhl_id)
    if (!award.pick || !p) return <p className="text-sm text-muted-foreground">Personne cette semaine.</p>
    return <PlayerRow player={p} detail={`${ord(award.pick.round, true)} ronde`} value={award.pick.value} valueLabel="pts" showManager />
  }
  const w = award[kind]
  const m = w && managerById(w.manager_id)
  if (!w || !m) return <p className="text-sm text-muted-foreground">Personne cette semaine.</p>
  const detail =
    kind === "comeback" && award.comeback
      ? `du ${ord(award.comeback.from)} au ${ord(award.comeback.to)} rang`
      : kind === "bad_luck"
        ? `environ ${fmt(w.value)} points perdus`
        : `${fmt(w.value)} points en 7 jours`
  return (
    <Item size="sm" className="px-0">
      <TeamAvatar id={m.id} name={m.name} size="sm" />
      <ItemContent className="min-w-0">
        <ItemTitle className="truncate">{m.name}</ItemTitle>
        <ItemDescription>{detail}</ItemDescription>
      </ItemContent>
    </Item>
  )
}

export default function AwardsPage() {
  const [latest, ...past] = POOL.awards
  return (
    <>
      <PageHeader
        title="Trophées"
        description={latest ? `Les honneurs de la semaine du ${dayLabel(latest.from)} au ${dayLabel(latest.to)}, remis chaque lundi.` : "Les honneurs de la semaine, remis chaque lundi."}
      />

      <div className="grid gap-3 sm:grid-cols-2">
        {AWARDS.map((a) => (
          <Card key={a.title} size="sm">
            <CardHeader>
              <CardTitle>{a.title}</CardTitle>
              <CardDescription>{a.description}</CardDescription>
              <CardAction><a.icon aria-hidden className="size-4 text-muted-foreground" /></CardAction>
            </CardHeader>
            <CardContent className="text-sm text-muted-foreground">
              {latest ? <Winner award={latest} kind={a.key} /> : "Premier gagnant après la semaine 1."}
            </CardContent>
          </Card>
        ))}
      </div>

      <HeadToHead />

      {latest ? (
        past.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle>Semaines précédentes</CardTitle>
              <CardDescription>Le pick de la semaine et la disette, semaine après semaine.</CardDescription>
            </CardHeader>
            <CardContent>
              <ItemGroup>
                {past.map((w) => {
                  const p = w.pick && playerById(w.pick.nhl_id)
                  const d = managerById(w.drought.manager_id)
                  return (
                    <Item key={w.week_end} size="sm" className="px-0">
                      <ItemContent className="min-w-0">
                        <ItemTitle>Semaine du {dayLabel(w.week_end)}</ItemTitle>
                        <ItemDescription className="truncate">
                          Pick : {p ? `${p.name} (${fmt(w.pick?.value)} pts)` : "personne"}. Disette : {d?.name}.
                        </ItemDescription>
                      </ItemContent>
                    </Item>
                  )
                })}
              </ItemGroup>
            </CardContent>
          </Card>
        )
      ) : (
        <Empty className="border">
          <EmptyHeader>
            <EmptyTitle>Les trophées commencent après la semaine 1</EmptyTitle>
            <EmptyDescription>
              La saison commence le {seasonStartLabel()}. Les premiers trophées seront remis le {firstAwardsLabel()}.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}
    </>
  )
}
