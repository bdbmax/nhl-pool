import Link from "next/link"

import { Badge } from "@/components/ui/badge"
import { Item, ItemActions, ItemContent, ItemDescription, ItemMedia, ItemTitle } from "@/components/ui/item"
import { PlayerAvatar } from "@/components/pool/player-avatar"
import { TeamCode, TeamMark } from "@/components/pool/team-avatar"
import { fmt, injuryLabel, managerById, playerHref, POS_SHORT, signed as signedFmt, type Player } from "@/lib/pool"

// Un joueur : photo, nom, équipe de la LNH et position, détail optionnel, et une valeur à droite.
// Toute la rangée mène à la page du joueur.
export function PlayerRow({
  player, rank, detail, value, valueLabel, showManager = false, variant = "default", signed = false, showInjury = true,
}: {
  player: Player
  rank?: number
  detail?: string
  value?: number | null
  valueLabel?: string
  showManager?: boolean
  variant?: "default" | "outline" | "muted"
  signed?: boolean
  showInjury?: boolean
}) {
  const mgr = showManager && player.manager_id ? managerById(player.manager_id) : undefined
  const bits = [player.nhl_team, POS_SHORT[player.pos], detail].filter(Boolean)
  const injury = showInjury ? injuryLabel(player.injury) : null
  return (
    <Item size="sm" variant={variant} render={<Link href={playerHref(player)} />}>
      {rank !== undefined && (
        <ItemMedia className="w-5 justify-start text-sm tabular-nums text-muted-foreground">{rank}</ItemMedia>
      )}
      <ItemMedia><PlayerAvatar player={player} size="sm" /></ItemMedia>
      <ItemContent className="min-w-0">
        {/* Rétro : le code du DG va à côté du nom (il tient toujours) ; Moderne : son nom, sous le joueur. */}
        <ItemTitle className="line-clamp-none flex! min-w-0 max-w-full">
          <span className="line-clamp-2 min-w-0 break-words">{player.name}</span>
          {mgr && <TeamCode id={mgr.id} />}
        </ItemTitle>
        <ItemDescription className="truncate">
          {bits.join(", ")}
          {mgr && <span data-slot="manager-in-description">, <TeamMark id={mgr.id} /> <span data-slot="manager-name">{mgr.name}</span></span>}
        </ItemDescription>
      </ItemContent>
      <ItemActions>
        {injury && <Badge variant="outline">{injury}</Badge>}
        {value !== undefined && (
          <span className="text-right text-sm tabular-nums">
            {signed ? signedFmt(value) : fmt(value)}
            {valueLabel && <span className="ml-auto block w-min text-xs leading-tight text-muted-foreground">{valueLabel}</span>}
          </span>
        )}
      </ItemActions>
    </Item>
  )
}
