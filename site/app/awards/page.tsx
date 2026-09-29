import {
  ActivityIcon, ArmchairIcon, BandageIcon, CrownIcon, FrownIcon, MedalIcon, MountainIcon, RocketIcon, SkullIcon, StarIcon,
  type LucideIcon,
} from "lucide-react"

import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty"
import { Item, ItemContent, ItemDescription, ItemGroup, ItemMedia, ItemTitle } from "@/components/ui/item"
import { PageHeader } from "@/components/pool/page-header"
import { HeadToHead } from "@/components/pool/head-to-head"
import { PlayerRow } from "@/components/pool/player-row"
import { TeamAvatar } from "@/components/pool/team-avatar"
import {
  type Award, dayLabel, firstAwardsLabel, fmt, managerById, ord, playerById, POOL, type SeasonAward, type SeasonEntry,
  seasonStartLabel,
} from "@/lib/pool"

// Chaque trophée est un classement : les 3 premiers, le 1er en évidence.
function Podium({ rows }: { rows: React.ReactNode[] }) {
  const shown = rows.filter(Boolean)
  if (!shown.length) return <p className="text-sm text-muted-foreground">Personne pour l&apos;instant.</p>
  return (
    <ol className="flex flex-col">
      {shown.map((c, i) => (
        <li key={i} data-slot="podium-row" data-place={i + 1} className="-ml-1 flex items-center gap-1">
          <span data-slot="podium-place" aria-label={`${ord(i + 1)} place`}
            className={i === 0 ? "w-3 shrink-0 text-sm font-semibold tabular-nums" : "w-3 shrink-0 text-sm tabular-nums text-muted-foreground"}>
            {i + 1}
          </span>
          <div className={i === 0 ? "min-w-0 flex-1" : "min-w-0 flex-1 opacity-80"}>{c}</div>
        </li>
      ))}
    </ol>
  )
}

function ManagerLine({ id, detail }: { id: number; detail: string }) {
  const m = managerById(id)
  if (!m) return null
  return (
    <Item size="sm" className="px-0">
      <ItemMedia><TeamAvatar id={m.id} name={m.name} size="sm" /></ItemMedia>
      <ItemContent className="min-w-0">
        <ItemTitle className="truncate">{m.name}</ItemTitle>
        <ItemDescription>{detail}</ItemDescription>
      </ItemContent>
    </Item>
  )
}

function AwardCard({ title, description, icon: Icon, children }: {
  title: string; description: string; icon: LucideIcon; children: React.ReactNode
}) {
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <CardDescription>{description}</CardDescription>
        <CardAction><Icon aria-hidden className="size-4 text-muted-foreground" /></CardAction>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  )
}

const pts = (n: number) => `${fmt(n)} pt${Math.abs(n) === 1 ? "" : "s"}`

// --- La semaine ---------------------------------------------------------------------------

const WEEKLY = [
  { key: "pick", title: "Pick de la semaine", description: "Les picks tardifs (9e ronde et plus loin) qui ont récolté le plus de points.", icon: CrownIcon },
  { key: "comeback", title: "Meilleure remontée", description: "Les équipes qui ont gagné le plus de rangs.", icon: RocketIcon },
  { key: "bad_luck", title: "Malchance", description: "Le plus de points projetés perdus à cause des blessures.", icon: BandageIcon },
  { key: "drought", title: "Disette", description: "Le moins de points au cours des 7 jours.", icon: SkullIcon },
] as const

function weekRows(award: Award, kind: (typeof WEEKLY)[number]["key"]): React.ReactNode[] {
  if (kind === "pick")
    return award.pick.map((x) => {
      const p = playerById(x.nhl_id)
      return p && <PlayerRow player={p} detail={`${ord(x.round, true)} ronde`} value={x.value} valueLabel="pts" showManager showInjury={false} />
    })
  if (kind === "comeback")
    return award.comeback.map((x) => <ManagerLine id={x.manager_id} detail={`du ${ord(x.from)} au ${ord(x.to)} rang`} />)
  if (kind === "bad_luck")
    return award.bad_luck.map((x) => (
      <ManagerLine id={x.manager_id} detail={`${fmt(x.games)} matchs manqués, environ ${pts(x.value)} perdus`} />
    ))
  return award.drought.map((x) => <ManagerLine id={x.manager_id} detail={`${pts(x.value)} en 7 jours`} />)
}

// --- La saison ----------------------------------------------------------------------------

const SEASON: Record<SeasonAward["key"], { title: string; description: string; icon: LucideIcon }> = {
  player: { title: "Joueur de l'année", description: "Les joueurs repêchés qui ont récolté le plus de points.", icon: StarIcon },
  pick: { title: "Pick de l'année", description: "Les meilleurs picks à partir de la 9e ronde.", icon: MedalIcon },
  bust: { title: "Déception de l'année", description: "Les picks des 3 premières rondes les plus loin sous la moyenne de leur ronde.", icon: FrownIcon },
  bad_luck: { title: "Malchance de l'année", description: "Le plus de matchs manqués par des joueurs blessés.", icon: BandageIcon },
  bench: { title: "Banc en or", description: "Le plus de points laissés sur le banc, marqués par des joueurs qui ne comptent pas.", icon: ArmchairIcon },
  king: { title: "Roi de la montagne", description: "Le plus de matins au 1er rang du classement.", icon: MountainIcon },
  rollercoaster: { title: "Montagnes russes", description: "Le plus de rangs gagnés et perdus depuis le début de la saison.", icon: ActivityIcon },
}

function seasonRow(k: SeasonAward["key"], x: SeasonEntry): React.ReactNode {
  const p = x.nhl_id ? playerById(x.nhl_id) : undefined
  if (k === "player" && p) return <PlayerRow player={p} value={x.value} valueLabel="pts" showManager showInjury={false} />
  if (k === "pick" && p) return <PlayerRow player={p} detail={`${ord(x.round ?? 0, true)} ronde`} value={x.value} valueLabel="pts" showManager showInjury={false} />
  if (k === "bust" && p)
    return <PlayerRow player={p} detail={`${ord(x.round ?? 0, true)} ronde, ${pts(x.value)}`} value={x.gap} valueLabel="écart" showManager signed showInjury={false} />
  if (k === "bad_luck") {
    const worst = x.worst ? playerById(x.worst.nhl_id) : undefined
    return <ManagerLine id={x.manager_id} detail={`${fmt(x.value)} matchs manqués, environ ${pts(x.points ?? 0)} perdus`
      + (worst && x.worst ? `, dont ${fmt(x.worst.games)} par ${worst.name}` : "")} />
  }
  if (k === "bench") {
    const best = x.best ? playerById(x.best.nhl_id) : undefined
    return <ManagerLine id={x.manager_id} detail={`${pts(x.value)} sur le banc` + (best && x.best ? `, dont ${pts(x.best.points)} de ${best.name}` : "")} />
  }
  if (k === "king") return <ManagerLine id={x.manager_id} detail={`${fmt(x.value)} matin${x.value > 1 ? "s" : ""} sur ${fmt(x.mornings)} au 1er rang`} />
  if (k === "rollercoaster") return <ManagerLine id={x.manager_id} detail={`${fmt(x.value)} rangs gagnés et perdus`} />
  return null
}

function SeasonAwards() {
  return (
    <section className="flex flex-col gap-3">
      <header className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold tracking-tight">Trophées de la saison</h2>
        <p className="text-sm text-muted-foreground">
          {POOL.season_awards.length
            ? "Le top 3 de chaque trophée jusqu'ici, mis à jour chaque matin. Remis pour de vrai à la fin de la saison."
            : "Dès le premier match, un top 3 par trophée, mis à jour chaque matin jusqu'à la fin de la saison."}
        </p>
      </header>
      <div className="grid gap-3 sm:grid-cols-2">
        {(Object.keys(SEASON) as SeasonAward["key"][]).map((key) => {
          const a = POOL.season_awards.find((x) => x.key === key)
          return (
            <AwardCard key={key} {...SEASON[key]}>
              <Podium rows={(a?.podium ?? []).map((x) => seasonRow(key, x))} />
            </AwardCard>
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
        description={latest
          ? `Les honneurs de la semaine du ${dayLabel(latest.from)} au ${dayLabel(latest.to)}, remis chaque lundi.`
          : "Les honneurs de la semaine, remis chaque lundi."}
      />

      {latest ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {WEEKLY.map((a) => (
            <AwardCard key={a.key} title={a.title} description={a.description} icon={a.icon}>
              <Podium rows={weekRows(latest, a.key)} />
            </AwardCard>
          ))}
        </div>
      ) : (
        <Empty className="border">
          <EmptyHeader>
            <EmptyTitle>Les trophées de la semaine commencent après la semaine 1</EmptyTitle>
            <EmptyDescription>
              La saison commence le {seasonStartLabel()}. Les premiers seront remis le {firstAwardsLabel()} : pick de la semaine,
              meilleure remontée, malchance et disette, chacun avec son top 3.
            </EmptyDescription>
          </EmptyHeader>
        </Empty>
      )}

      <SeasonAwards />

      <HeadToHead />

      {past.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Semaines précédentes</CardTitle>
            <CardDescription>Le pick de la semaine et la disette, semaine après semaine.</CardDescription>
          </CardHeader>
          <CardContent>
            <ItemGroup>
              {past.map((w) => {
                const p = w.pick[0] && playerById(w.pick[0].nhl_id)
                const d = w.drought[0] && managerById(w.drought[0].manager_id)
                return (
                  <Item key={w.week_end} size="sm" className="px-0">
                    <ItemContent className="min-w-0">
                      <ItemTitle>Semaine du {dayLabel(w.week_end)}</ItemTitle>
                      <ItemDescription className="truncate">
                        Pick : {p ? `${p.name} (${pts(w.pick[0].value)})` : "personne"}. Disette : {d ? d.name : "personne"}.
                      </ItemDescription>
                    </ItemContent>
                  </Item>
                )
              })}
            </ItemGroup>
          </CardContent>
        </Card>
      )}
    </>
  )
}
