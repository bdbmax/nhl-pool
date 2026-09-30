import { SwordsIcon, TvIcon } from "lucide-react"

import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Item, ItemContent, ItemDescription, ItemGroup, ItemTitle } from "@/components/ui/item"
import { PlayerRow } from "@/components/pool/player-row"
import { TeamAvatar } from "@/components/pool/team-avatar"
import { dayLabel, fmt, gameTime, managerById, playerById, POOL, type RaceSide } from "@/lib/pool"

// Page d'équipe : qui joue aujourd'hui (daily.tonight, la date du jour même après minuit). Ceux qui comptent d'abord.
export function TonightCard({ id }: { id: number }) {
  const t = POOL.tonight
  if (!t) return null
  const games = t.managers[String(id)] ?? []
  const counted = games.filter((g) => g.counts).length
  return (
    <Card>
      <CardHeader>
        <CardTitle>Aujourd'hui</CardTitle>
        <CardDescription>
          {games.length
            ? `${counted} joueur${counted > 1 ? "s" : ""} qui compte${counted > 1 ? "nt" : ""} en action le ${dayLabel(t.date)}`
              + (games.length > counted ? `, et ${games.length - counted} au banc.` : ".")
            : `Aucun de tes joueurs ne joue le ${dayLabel(t.date)}.`}
        </CardDescription>
        <CardAction><TvIcon aria-hidden className="size-4 text-muted-foreground" /></CardAction>
      </CardHeader>
      {games.length > 0 && (
        <CardContent>
          <ItemGroup>
            {games.map((g) => {
              const p = playerById(g.nhl_id)
              return p ? (
                <PlayerRow key={g.nhl_id} player={p} variant={g.counts ? "default" : "muted"}
                  detail={`${g.home ? "contre" : "à"} ${g.opp}, ${gameTime(g.start)}${g.counts ? "" : " (banc)"}`} />
              ) : null
            })}
          </ItemGroup>
        </CardContent>
      )}
    </Card>
  )
}

function weeks(w: number) {
  return w < 1 ? "moins d'une semaine" : `environ ${fmt(w, 0)} semaine${Math.round(w) > 1 ? "s" : ""}`
}

function Rival({ side, label }: { side: RaceSide; label: "devant" | "derrière" }) {
  const m = managerById(side.manager_id)
  if (!m) return null
  const games = side.left_diff === 0 ? "autant de matchs à jouer"
    : `${fmt(Math.abs(side.left_diff))} match${Math.abs(side.left_diff) > 1 ? "s" : ""} à jouer de ${side.left_diff > 0 ? "plus" : "moins"} que lui`
  return (
    <Item size="sm" className="px-0">
      <TeamAvatar id={m.id} name={m.name} size="sm" />
      <ItemContent className="min-w-0">
        <ItemTitle className="truncate">{label === "devant" ? "Devant toi" : "Derrière toi"} : {m.name}</ItemTitle>
        <ItemDescription className="line-clamp-none">
          {side.gap === 0 ? "À égalité" : `${fmt(side.gap)} pt${side.gap > 1 ? "s" : ""} ${label === "devant" ? "devant" : "derrière"}`},
          {" "}{games}{side.ppg != null ? `, ${fmt(side.ppg, 2)} pt par match` : ""}.
        </ItemDescription>
      </ItemContent>
    </Item>
  )
}

// Page d'équipe : l'équipe juste devant et juste derrière, et quand l'écart se comble au rythme actuel (daily.race).
export function RaceCard({ id }: { id: number }) {
  const r = POOL.race?.[String(id)]
  if (!r) return null
  const ahead = r.ahead && managerById(r.ahead.manager_id)
  const behind = r.behind && managerById(r.behind.manager_id)
  const lines = [
    r.ahead ? (r.catch_weeks != null
      ? `À ton rythme actuel, tu rattrapes ${ahead?.name} dans ${weeks(r.catch_weeks)}.`
      : `À ce rythme, tu ne rattrapes pas ${ahead?.name} d'ici la fin de la saison.`)
      : "Tu mènes le pool.",
    r.behind && r.caught_weeks != null ? `À son rythme, ${behind?.name} te rattrape dans ${weeks(r.caught_weeks)}.` : null,
  ].filter(Boolean)
  return (
    <Card>
      <CardHeader>
        <CardTitle>Ta course</CardTitle>
        <CardDescription>Le rythme compte les 11 joueurs qui comptent : points par match joué et matchs à jouer d&apos;ici la fin.</CardDescription>
        <CardAction><SwordsIcon aria-hidden className="size-4 text-muted-foreground" /></CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <ItemGroup>
          {r.ahead && <Rival side={r.ahead} label="devant" />}
          {r.behind && <Rival side={r.behind} label="derrière" />}
        </ItemGroup>
        <div className="flex flex-col gap-1 text-sm">{lines.map((l) => <p key={l}>{l}</p>)}</div>
      </CardContent>
    </Card>
  )
}
