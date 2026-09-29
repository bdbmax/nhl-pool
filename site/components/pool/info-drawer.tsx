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
  today: {
    button: "Comment fonctionne le classement",
    title: "Le classement d'aujourd'hui",
    summary: "Les vrais points de la LNH, mis à jour chaque matin à 5 h 30.",
    points: [
      "Les statistiques viennent de la LNH et comprennent tous les matchs joués jusqu'à la veille.",
      "Attaquants : 1 point par but et par passe, 1 de plus par but gagnant et par tour du chapeau. Défenseurs : 2 points par but, 1 par passe, 1 de plus par but gagnant. Gardiens : 2 points par victoire, 1 par défaite en prolongation ou en tirs de barrage, 3 de plus par blanchissage.",
      "Chaque équipe compte ses 6 meilleurs attaquants, ses 4 meilleurs défenseurs et son meilleur gardien à ce jour.",
      "En cas d'égalité, la meilleure projection finale passe devant.",
    ],
  },
} as const

export function InfoDrawer({ topic }: { topic: keyof typeof TOPICS }) {
  const t = TOPICS[topic]
  return (
    <Drawer>
      <DrawerTrigger render={<Button variant="ghost" size="icon-sm" aria-label={t.button} />}>
        <CircleHelpIcon />
      </DrawerTrigger>
      <DrawerContent>
        {/* Titre et bouton fixes ; la liste défile entre les deux quand elle dépasse l'écran. */}
        <div className="mx-auto flex min-h-0 w-full max-w-md flex-1 flex-col">
          <DrawerHeader>
            <DrawerTitle>{t.title}</DrawerTitle>
            <DrawerDescription>{t.summary}</DrawerDescription>
          </DrawerHeader>
          <ul className="flex min-h-0 list-disc flex-col gap-2 overflow-y-auto overscroll-contain px-8 pb-2 text-sm text-muted-foreground">
            {t.points.map((p) => <li key={p}>{p}</li>)}
          </ul>
          <DrawerFooter>
            <DrawerClose render={<Button variant="outline" />}>Compris</DrawerClose>
          </DrawerFooter>
        </div>
      </DrawerContent>
    </Drawer>
  )
}
