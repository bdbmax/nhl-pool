import {
  ActivityIcon, BandageIcon, CrownIcon, FrownIcon, MedalIcon, MountainIcon, RocketIcon, SkullIcon, StarIcon,
} from "lucide-react"

import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Item, ItemContent, ItemDescription, ItemGroup, ItemTitle } from "@/components/ui/item"
import { PageHeader } from "@/components/pool/page-header"
import { HeadToHead } from "@/components/pool/head-to-head"
import { PlayerRow } from "@/components/pool/player-row"
import { TeamAvatar } from "@/components/pool/team-avatar"
import {
  type Award, dayLabel, firstAwardsLabel, fmt, managerById, ord, playerById, POOL, type SeasonAward, seasonStartLabel,
} from "@/lib/pool"

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
        ? `${award.bad_luck?.games ? `${fmt(award.bad_luck.games)} matchs manqués, ` : ""}environ ${fmt(w.value)} points perdus`
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

// Trophées de la saison : recalculés chaque matin à partir de l'historique (daily.season_awards).
const SEASON = {
  player: { title: "Joueur de l'année", description: "Le joueur repêché qui a récolté le plus de points.", icon: StarIcon },
  pick: { title: "Pick de l'année", description: "Le meilleur pick à partir de la 9e ronde.", icon: MedalIcon },
  bust: { title: "Déception de l'année", description: "Le pick des 3 premières rondes le plus loin sous la moyenne de sa ronde.", icon: FrownIcon },
  bad_luck: { title: "Malchance de l'année", description: "Le plus de matchs manqués par des joueurs blessés.", icon: BandageIcon },
  king: { title: "Roi de la montagne", description: "Le plus de matins au 1er rang du classement.", icon: MountainIcon },
  rollercoaster: { title: "Montagnes russes", description: "Le plus de rangs gagnés et perdus depuis le début de la saison.", icon: ActivityIcon },
} as const

function ManagerLine({ id, detail }: { id: number; detail: string }) {
  const m = managerById(id)
  if (!m) return null
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

function SeasonWinner({ a }: { a: SeasonAward }) {
  const p = a.nhl_id ? playerById(a.nhl_id) : undefined
  if (a.key === "player" && p) return <PlayerRow player={p} value={a.value} valueLabel="pts" showManager />
  if (a.key === "pick" && p) return <PlayerRow player={p} detail={`${ord(a.round ?? 0, true)} ronde`} value={a.value} valueLabel="pts" showManager />
  if (a.key === "bust" && p)
    return <PlayerRow player={p} detail={`${ord(a.round ?? 0, true)} ronde, ${fmt(a.value)} ${a.value === 1 ? "pt" : "pts"}`} value={a.gap} valueLabel="écart" showManager signed />
  if (a.key === "bad_luck") {
    const worst = a.worst ? playerById(a.worst.nhl_id) : undefined
    return (
      <ManagerLine id={a.manager_id} detail={`${fmt(a.value)} matchs manqués, environ ${fmt(a.points)} points perdus`
        + (worst && a.worst ? `, dont ${fmt(a.worst.games)} par ${worst.name}` : "")} />
    )
  }
  if (a.key === "king") return <ManagerLine id={a.manager_id} detail={`${fmt(a.value)} matin${a.value > 1 ? "s" : ""} sur ${fmt(a.mornings)} au 1er rang`} />
  if (a.key === "rollercoaster") return <ManagerLine id={a.manager_id} detail={`${fmt(a.value)} rangs gagnés et perdus`} />
  return null
}

function SeasonAwards() {
  return (
    <section className="flex flex-col gap-3">
      <header className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold tracking-tight">Trophées de la saison</h2>
        <p className="text-sm text-muted-foreground">
          {POOL.season_awards.length
            ? "La course jusqu'ici, mise à jour chaque matin. Remis pour de vrai à la fin de la saison."
            : "Dès le premier match, mis à jour chaque matin jusqu'à la fin de la saison."}
        </p>
      </header>
      <div className="grid gap-3 sm:grid-cols-2">
        {(Object.keys(SEASON) as (keyof typeof SEASON)[]).map((key) => {
          const t = SEASON[key]
          const a = POOL.season_awards.find((x) => x.key === key)
          return (
            <Card key={key} size="sm">
              <CardHeader>
                <CardTitle>{t.title}</CardTitle>
                <CardDescription>{t.description}</CardDescription>
                <CardAction><t.icon aria-hidden className="size-4 text-muted-foreground" /></CardAction>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground">
                {a ? <SeasonWinner a={a} /> : "Personne pour l'instant."}
              </CardContent>
            </Card>
          )
        })}
      </div>
    </section>
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

      <SeasonAwards />

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
