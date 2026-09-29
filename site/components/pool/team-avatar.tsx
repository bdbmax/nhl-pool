import type { CSSProperties } from "react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { EMBLEMS } from "@/lib/emblems"
import { codeTextColor, jerseyImage, jerseyOf } from "@/lib/jerseys"
import { cn } from "@/lib/utils"

// Chandail pixel de l'habillage Rétro. Caché en Moderne ; l'image n'est chargée qu'en Rétro (app/skins.css).
function Jersey({ id }: { id: number }) {
  return <span aria-hidden data-slot="team-jersey" className="hidden" style={{ "--jersey": jerseyImage(id, "badge") } as CSSProperties} />
}

// L'emblème d'une équipe : un carré à sa couleur, avec son icône. En Rétro, son chandail.
export function TeamAvatar({ id, name, size = "default" }: { id: number; name: string; size?: "sm" | "default" | "lg" }) {
  const e = EMBLEMS[id]
  const Icon = e?.icon
  return (
    <Avatar size={size} role="img" aria-label={`${name}, emblème ${e?.label ?? ""}`.trim()} className="rounded-md after:rounded-md">
      <AvatarFallback className={cn("rounded-md text-team-fg", e?.bg)}>
        {Icon && <Icon aria-hidden className={cn(size === "lg" ? "size-5" : size === "sm" ? "size-3.5" : "size-4")} />}
      </AvatarFallback>
      <Jersey id={id} />
    </Avatar>
  )
}

// Petit emblème à côté du nom d'un DG dans le texte.
export function TeamMark({ id }: { id: number }) {
  const e = EMBLEMS[id]
  const Icon = e?.icon
  return Icon ? (
    <span aria-hidden data-slot="team-mark" className={cn("relative inline-flex size-4 items-center justify-center rounded-sm align-[-3px] text-team-fg", e.bg)}>
      <Icon className="size-3" />
      <Jersey id={id} />
    </span>
  ) : null
}

// Code de 3 lettres façon tableau indicateur, aux couleurs du chandail. Visible seulement en Rétro.
export function TeamCode({ id }: { id: number }) {
  const j = jerseyOf(id)
  return j ? (
    <span data-slot="team-code" className="hidden" style={{ background: j.main, color: codeTextColor(j) }}>
      {j.code}
    </span>
  ) : null
}
