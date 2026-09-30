"use client"

import { CircleHelpIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Drawer, DrawerClose, DrawerContent, DrawerDescription, DrawerFooter, DrawerHeader, DrawerTitle, DrawerTrigger,
} from "@/components/ui/drawer"
import { fmt, listJoin, MANAGERS, pct, POOL } from "@/lib/pool"

const SOURCES = listJoin(POOL.projection_sources)
const K = POOL.real_weight_games
// Exemples tirés des chiffres du jour : l'équipe projetée au 1er rang.
const LEAD = [...MANAGERS].sort((a, b) => a.proj_rank - b.proj_rank)[0]

const TOPICS = {
  projected: {
    button: "Comment fonctionnent les projections",
    title: "D'où viennent les projections",
    summary: `La moyenne de quatre projections externes : ${SOURCES}.`,
    points: [
      "Les buts, les passes, les victoires, les défaites en prolongation et les blanchissages projetés par chaque source sont comptés selon les règles du pool.",
      "Quand une source ne projette pas quelque chose, comme les buts gagnants, les tours du chapeau ou les blanchissages, on utilise les vrais taux de la ligue la saison dernière.",
      "Chaque source est ramenée à un rythme par match (par départ pour les gardiens). Une fois la saison commencée, ce rythme est mis à jour avec le vrai rythme du joueur, pondéré par ses matchs joués : "
        + `après ${K} matchs, le vrai rythme compte autant que la projection.`,
      "Les matchs restants : ceux de son équipe de la LNH, selon la part des matchs que la projection d'ESPN (sinon CBS) lui donne, moins les absences prévues (10 matchs pour un blessé, 3 pour un absent ou un suspendu, 1 pour un incertain).",
      "Pour les gardiens, la part des départs projetée est mise à jour avec sa vraie part des départs de son équipe.",
      "La projection finale, ce sont les vrais points récoltés, plus la projection des matchs restants. Les sources sont mises à jour chaque matin.",
      "Seuls les 6 meilleurs attaquants, les 4 meilleurs défenseurs et le meilleur gardien de chaque équipe comptent.",
      "Pourquoi simuler 20 000 saisons plutôt qu'additionner les projections ? Parce qu'au pool, seuls les meilleurs comptent à la fin. Si un partant se blesse ou tombe en panne, un réserviste qui connaît une bonne saison prend sa place. La simple somme des projections ignore cette valeur du banc ; la simulation la compte.",
      `Exemple : pour ${LEAD.name}, la somme des projections des 11 joueurs qui comptent donne ${fmt(LEAD.proj_consensus)} points, mais la moyenne des saisons simulées est de ${fmt(LEAD.expected_total)} points. La différence, c'est la profondeur de son banc.`,
    ],
  },
  odds: {
    button: "Comment fonctionnent les odds",
    title: "Comment on calcule les odds",
    summary: "20 000 saisons simulées, à partir de projections externes et de vrais résultats de la LNH.",
    points: [
      `Dans chaque saison, les quatre sources (${SOURCES}) reçoivent un poids au hasard, puisque personne ne sait laquelle va viser juste cette année.`,
      "La saison de chaque joueur est ensuite ajustée à la hausse ou à la baisse selon une vraie variation, tirée de l'évolution des joueurs de la LNH d'une saison à l'autre au cours des trois dernières saisons. Ça tient compte des blessures, des passages à vide, des éclosions et des gardiens qui perdent leur poste.",
      "Les alignements sont fixes, et seuls les 6 meilleurs attaquants, les 4 meilleurs défenseurs et le meilleur gardien comptent.",
      "Les odds de gagner, c'est la proportion des saisons simulées où l'équipe termine au premier rang.",
      `Pourquoi pas juste les projections ? Une projection dit combien de points une équipe devrait faire, pas ses chances de finir premier. ${LEAD.name} est projeté au 1er rang, mais ne gagne que ${pct(LEAD.win_pct)} des saisons simulées : les autres équipes sont assez proches pour que les blessures et les séquences chaudes changent l'ordre.`,
      "Avec 20 000 saisons, les pourcentages restent stables à environ un demi-point près d'un matin à l'autre. Quand ils bougent, c'est à cause des vrais matchs, pas du hasard de la simulation.",
      "Une fois la saison commencée, les points déjà récoltés sont comptés tels quels, et seuls les matchs restants sont projetés. La variation d'une saison à l'autre rétrécit avec la part de la saison qui reste. Les odds deviennent donc plus précises au fil de la saison.",
    ],
  },
  pace: {
    button: "Comment fonctionne le rythme",
    title: "Le rythme de chaque équipe",
    summary: "Qui produit le plus par match, et qui a encore le plus de matchs à jouer.",
    points: [
      "Les deux chiffres portent sur les 11 joueurs qui comptent pour l'équipe (les badges « Compte » de sa page).",
      "Pts par match : leurs vrais points divisés par les matchs qu'ils ont joués. Un match manqué à cause d'une blessure ne compte pas, donc c'est le rythme quand ils jouent.",
      "Matchs à jouer : les matchs qui restent au calendrier de leurs équipes de la LNH d'ici la fin de la saison, blessés compris, puisqu'ils vont revenir. Entre parenthèses, l'écart avec la moyenne des 12 équipes.",
      "Une équipe en retard au classement, mais avec un bon rythme et plus de matchs à jouer que les autres, a de bonnes chances de remonter. Les odds en tiennent déjà compte.",
    ],
  },
  today: {
    button: "Comment fonctionne le classement",
    title: "Le classement d'aujourd'hui",
    summary: "Les vrais points de la LNH, mis à jour chaque matin à 5 h 30, et vers 22 h avec les matchs du soir.",
    points: [
      "Les statistiques viennent de la LNH. Le matin, elles comprennent tous les matchs joués jusqu'à la veille. Vers 22 h, les matchs de la soirée qui sont terminés s'ajoutent ; la mise à jour du matin reste la version officielle.",
      "Les petites flèches montrent les rangs gagnés ou perdus depuis la mise à jour précédente.",
      "Sous chaque équipe, par exemple « 17/24 à jouer cette sem. » : il reste 17 matchs à jouer sur les 24 de la semaine (du lundi au dimanche), additionnés pour les 11 joueurs qui comptent, sans les blessés et les absents. Plus de matchs, plus de chances de remonter.",
      "Ce sont des points de pool, pas les points de la LNH. Attaquants : 1 point par but et par passe, 1 de plus par but gagnant et par tour du chapeau. Défenseurs : 2 points par but, 1 par passe, 1 de plus par but gagnant. Gardiens : 2 points par victoire, 1 par défaite en prolongation ou en tirs de barrage, 3 de plus par blanchissage.",
      "Chaque équipe compte ses 6 meilleurs attaquants, ses 4 meilleurs défenseurs et son meilleur gardien à ce jour.",
      "En cas d'égalité, la meilleure projection finale passe devant.",
    ],
  },
} as const

// Le bouton "?" (icon, dans les cartes) ou un lien texte (link, sous les onglets du classement).
export function InfoDrawer({ topic, variant = "icon" }: { topic: keyof typeof TOPICS; variant?: "icon" | "link" }) {
  const t = TOPICS[topic]
  return (
    <Drawer showSwipeHandle>
      {variant === "link" ? (
        <DrawerTrigger render={<Button variant="link" size="sm" data-slot="info-link" className="h-auto gap-1 px-0 text-xs text-muted-foreground" />}>
          <CircleHelpIcon aria-hidden className="size-3.5" />
          {t.button}
        </DrawerTrigger>
      ) : (
        <DrawerTrigger render={<Button variant="ghost" size="icon-sm" aria-label={t.button} />}>
          <CircleHelpIcon />
        </DrawerTrigger>
      )}
      <DrawerContent data-info-drawer="">
        {/* Titre et bouton fixes ; les étapes défilent entre les deux quand elles dépassent l'écran. */}
        <div className="mx-auto flex min-h-0 w-full max-w-md flex-1 flex-col">
          <DrawerHeader className="gap-2 px-6 pt-6 text-left group-data-[swipe-axis=y]/drawer-popup:text-left">
            <span data-slot="info-kicker" className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
              Comment ça marche
            </span>
            <DrawerTitle className="text-xl leading-tight font-semibold">{t.title}</DrawerTitle>
            <DrawerDescription className="text-sm text-foreground">{t.summary}</DrawerDescription>
          </DrawerHeader>
          <ol className="mt-4 flex min-h-0 flex-col overflow-y-auto overscroll-contain border-t px-6 text-sm">
            {t.points.map((p, i) => (
              <li key={p} data-slot="info-step" className="flex gap-3 border-b py-3 last:border-b-0">
                <span data-slot="info-step-number" aria-hidden
                  className="flex size-6 shrink-0 items-center justify-center rounded-full bg-foreground text-xs font-semibold text-background tabular-nums">
                  {i + 1}
                </span>
                <span className="text-muted-foreground">{p}</span>
              </li>
            ))}
          </ol>
          <DrawerFooter className="border-t px-6 pt-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
            <DrawerClose render={<Button size="lg" className="w-full" />}>Compris</DrawerClose>
          </DrawerFooter>
        </div>
      </DrawerContent>
    </Drawer>
  )
}
