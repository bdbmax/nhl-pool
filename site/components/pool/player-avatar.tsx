import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { initials, type Player } from "@/lib/pool"

// Official NHL headshot (keyed by NHL id). If it fails to load, Avatar shows the initials.
export function PlayerAvatar({ player, size = "default", className }: {
  player: Player; size?: "sm" | "default" | "lg"; className?: string
}) {
  return (
    <Avatar size={size} className={className}>
      {player.photo && <AvatarImage src={player.photo} alt="" loading="lazy" />}
      <AvatarFallback>{initials(player.name)}</AvatarFallback>
    </Avatar>
  )
}
