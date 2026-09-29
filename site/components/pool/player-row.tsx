import { Badge } from "@/components/ui/badge"
import { Item, ItemActions, ItemContent, ItemDescription, ItemMedia, ItemTitle } from "@/components/ui/item"
import { PlayerAvatar } from "@/components/pool/player-avatar"
import { TeamCode, TeamMark } from "@/components/pool/team-avatar"
import { fmt, injuryLabel, managerById, POS_SHORT, signed as signedFmt, type Player } from "@/lib/pool"

// Un joueur : photo, nom, équipe de la LNH et position, détail optionnel, et une valeur à droite.
export function PlayerRow({
  player, rank, detail, value, valueLabel, showManager = false, variant = "default", signed = false,
}: {
  player: Player
  rank?: number
  detail?: string
  value?: number | null
  valueLabel?: string
  showManager?: boolean
  variant?: "default" | "outline" | "muted"
  signed?: boolean
}) {
  const mgr = showManager && player.manager_id ? managerById(player.manager_id) : undefined
  const bits = [player.nhl_team, POS_SHORT[player.pos], detail].filter(Boolean)
  const injury = injuryLabel(player.injury)
  return (
    <Item size="sm" variant={variant}>
      {rank !== undefined && (
        <ItemMedia className="w-5 justify-start text-sm tabular-nums text-muted-foreground">{rank}</ItemMedia>
      )}
      <ItemMedia><PlayerAvatar player={player} size="sm" /></ItemMedia>
      <ItemContent className="min-w-0">
        <ItemTitle className="truncate">{player.name}</ItemTitle>
        <ItemDescription className="truncate">
          {bits.join(", ")}
          {mgr && <>, <TeamMark id={mgr.id} /> <span data-slot="manager-name">{mgr.name}</span><TeamCode id={mgr.id} /></>}
        </ItemDescription>
      </ItemContent>
      <ItemActions>
        {injury && <Badge variant="outline">{injury}</Badge>}
        {value !== undefined && (
          <span className="text-right text-sm tabular-nums">
            {signed ? signedFmt(value) : fmt(value)}
            {valueLabel && <span className="block text-xs text-muted-foreground">{valueLabel}</span>}
          </span>
        )}
      </ItemActions>
    </Item>
  )
}
