import Link from "next/link"
import { NewspaperIcon } from "lucide-react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardAction,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { ItemGroup } from "@/components/ui/item"
import { PlayerRow } from "@/components/pool/player-row"
import { dayLabel, fmt, managerById, ord, playerById, signed } from "@/lib/pool"
import type { Edition, TeamRecap } from "@/lib/recaps"

export function RecapSummary({
  edition,
  link = true,
}: {
  edition: Edition
  link?: boolean
}) {
  const sorted = [...edition.teams].sort(
    (a, b) => b.gain - a.gain || a.rank - b.rank
  )
  const best = sorted.filter((t) => t.gain === sorted[0].gain)
  const climb = [...sorted].sort(
    (a, b) => b.previousRank - b.rank - (a.previousRank - a.rank)
  )[0]
  const star = edition.teams
    .flatMap((t) => t.players.map((p) => ({ ...p, team: t.id })))
    .sort((a, b) => b.points - a.points)[0]
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>Le quotidien · {dayLabel(edition.to)}</CardTitle>
        <CardAction>
          <NewspaperIcon aria-hidden className="size-4 text-muted-foreground" />
        </CardAction>
      </CardHeader>
      <CardContent>
        <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm">
          <li>
            {best.map((t) => managerById(t.id)?.name).join(" et ")} :{" "}
            {signed(sorted[0].gain)} points au classement, la meilleure
            progression.
          </li>
          {climb.previousRank > climb.rank && (
            <li>
              {managerById(climb.id)?.name} gagne{" "}
              {climb.previousRank - climb.rank} rang
              {climb.previousRank - climb.rank === 1 ? "" : "s"}, du{" "}
              {ord(climb.previousRank)} au {ord(climb.rank)}.
            </li>
          )}
          {star && star.points > 0 && (
            <li>
              {playerById(star.id)?.name} ({managerById(star.team)?.name}) :{" "}
              {fmt(star.points)} points de pool.
            </li>
          )}
        </ul>
      </CardContent>
      {link && (
        <CardFooter>
          <Button
            size="sm"
            variant="outline"
            render={<Link href="/daily/" />}
            nativeButton={false}
          >
            Lire le quotidien →
          </Button>
        </CardFooter>
      )}
    </Card>
  )
}

export function TeamDailyRecap({
  edition,
  team,
  full = false,
}: {
  edition: Edition
  team: TeamRecap
  full?: boolean
}) {
  const scorers = team.players.filter((p) => p.points !== 0)
  const participants = team.players.filter((p) => p.games > 0 || p.points !== 0)
  const absent = team.players.filter(
    (p) => p.games === 0 && p.points === 0
  ).length
  const lines = full ? participants : participants.slice(0, 3)
  return (
    <Card size="sm">
      <CardHeader>
        <CardTitle>
          {full
            ? `La soirée de ${managerById(team.id)?.name}`
            : `La soirée du ${dayLabel(edition.to)}`}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <div className="grid grid-cols-3 gap-2 text-sm tabular-nums">
          <div>
            <strong className="font-medium">
              {signed(team.gain)} pts pool
            </strong>
            <p className="text-xs text-muted-foreground">
              {team.before} → {team.points} au total
            </p>
          </div>
          <div>
            <strong className="font-medium">
              {ord(team.previousRank)} → {ord(team.rank)}
            </strong>
            <p className="text-xs text-muted-foreground">Rang au classement</p>
          </div>
          <div>
            <strong className="font-medium">
              {team.players.reduce((s, p) => s + Math.max(0, p.games), 0)}
            </strong>
            <p className="text-xs text-muted-foreground">Matchs de joueurs</p>
          </div>
        </div>
        {!scorers.length && (
          <p className="text-sm text-muted-foreground">
            Aucun point de pool produit pendant cette période.
          </p>
        )}
        <ItemGroup>
          {lines.map((p) => {
            const player = playerById(p.id)
            return player ? (
              <div key={p.id}>
                <PlayerRow
                  signed
                  showInjury={false}
                  player={player}
                  value={p.points}
                  valueLabel="pts pool"
                />
                {full && p.stats && (
                  <p className="pb-2 text-xs text-muted-foreground">
                    {p.stats
                      ? `${
                          Object.entries(p.stats)
                            .filter(([, v]) => v !== 0)
                            .map(
                              ([k, v]) =>
                                `${v} ${{ G: "but(s)", A: "passe(s)", GWG: "but(s) gagnant(s)", HT: "tour(s) du chapeau", W: "victoire(s)", OTL: "défaite(s) en prolongation", SO: "blanchissage(s)" }[k] ?? k}`
                            )
                            .join(", ") || "aucun événement de pointage"
                        }`
                      : ""}
                  </p>
                )}
              </div>
            ) : null
          })}
        </ItemGroup>
        {team.production !== team.gain && (
          <p className="text-xs text-muted-foreground">
            {team.production} points produits par les joueurs; {team.gain}{" "}
            ajoutés au classement après recalcul des 6 attaquants, 4 défenseurs
            et 1 gardien qui comptent. Les corrections statistiques peuvent
            aussi modifier ces totaux.
          </p>
        )}
        {full && absent > 0 && (
          <p className="text-xs text-muted-foreground">
            {absent} joueurs sans match dans cette période.
          </p>
        )}
      </CardContent>
      {!full && (
        <CardFooter>
          <Button
            size="sm"
            variant="outline"
            render={<Link href={`/daily/?team=${team.id}`} />}
            nativeButton={false}
          >
            Voir le détail de la soirée →
          </Button>
        </CardFooter>
      )}
    </Card>
  )
}
