import {
  AnchorIcon, BirdIcon, CrownIcon, FishIcon, FlameIcon, GhostIcon, MountainIcon,
  RocketIcon, SnowflakeIcon, SwordsIcon, TargetIcon, ZapIcon, type LucideIcon,
} from "lucide-react"

// One emblem and one color per team, keyed by draft slot (1-12). Colors are theme
// variables (--team-N in app/globals.css), with lighter versions in dark mode. In Rétro,
// --team-N is the jersey color instead (teamColorStyle in lib/jerseys.ts).
// Class names are written out in full so Tailwind can find them.
export const EMBLEMS: Record<number, { icon: LucideIcon; label: string; bg: string; text: string }> = {
  1: { icon: CrownIcon, label: "Couronne", bg: "bg-team-1", text: "text-team-1" },
  2: { icon: FlameIcon, label: "Flamme", bg: "bg-team-2", text: "text-team-2" },
  3: { icon: SnowflakeIcon, label: "Flocon", bg: "bg-team-3", text: "text-team-3" },
  4: { icon: ZapIcon, label: "Éclair", bg: "bg-team-4", text: "text-team-4" },
  5: { icon: AnchorIcon, label: "Ancre", bg: "bg-team-5", text: "text-team-5" },
  6: { icon: RocketIcon, label: "Fusée", bg: "bg-team-6", text: "text-team-6" },
  7: { icon: MountainIcon, label: "Montagne", bg: "bg-team-7", text: "text-team-7" },
  8: { icon: BirdIcon, label: "Oiseau", bg: "bg-team-8", text: "text-team-8" },
  9: { icon: FishIcon, label: "Poisson", bg: "bg-team-9", text: "text-team-9" },
  10: { icon: GhostIcon, label: "Fantôme", bg: "bg-team-10", text: "text-team-10" },
  11: { icon: SwordsIcon, label: "Épées", bg: "bg-team-11", text: "text-team-11" },
  12: { icon: TargetIcon, label: "Cible", bg: "bg-team-12", text: "text-team-12" },
}
