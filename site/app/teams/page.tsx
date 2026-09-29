import Link from "next/link"
import { ChevronRightIcon } from "lucide-react"

import { Item, ItemActions, ItemContent, ItemDescription, ItemGroup, ItemMedia, ItemSeparator, ItemTitle } from "@/components/ui/item"
import { PageHeader } from "@/components/pool/page-header"
import { TeamAvatar, TeamCode } from "@/components/pool/team-avatar"
import { fmt, MANAGERS, ord, pct } from "@/lib/pool"

export default function TeamsPage() {
  const teams = [...MANAGERS].sort((a, b) => a.slot - b.slot)
  return (
    <>
      <PageHeader
        title="Équipes"
        description="Douze DG, 16 picks chacun, dans l'ordre du draft. Touche une équipe pour voir son alignement."
      />
      <ItemGroup>
        {teams.map((m, i) => (
          <div key={m.id}>
            {i > 0 && <ItemSeparator />}
            <Item render={<Link href={`/teams/${m.id}`} />}>
              <ItemMedia><TeamAvatar id={m.id} name={m.name} /></ItemMedia>
              <ItemContent>
                <ItemTitle>{m.name}<TeamCode id={m.id} /></ItemTitle>
                <ItemDescription>{ord(m.slot)} pick, projection de {fmt(m.expected_total)} points</ItemDescription>
              </ItemContent>
              <ItemActions>
                <span className="text-sm tabular-nums">{pct(m.win_pct)}</span>
                <ChevronRightIcon aria-hidden className="size-4 text-muted-foreground" />
              </ItemActions>
            </Item>
          </div>
        ))}
      </ItemGroup>
    </>
  )
}
