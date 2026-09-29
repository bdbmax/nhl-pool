import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { initials, type Player } from "@/lib/pool"

// Official NHL headshot (keyed by NHL id). If it fails to load, Avatar shows the initials.
export function PlayerAvatar({ player, size = "default" }: { player: Player; size?: "sm" | "default" | "lg" }) {
  return (
    <Avatar size={size}>
      {player.photo && <AvatarImage src={player.photo} alt="" loading="lazy" />}
      <AvatarFallback>{initials(player.name)}</AvatarFallback>
    </Avatar>
  )
}
