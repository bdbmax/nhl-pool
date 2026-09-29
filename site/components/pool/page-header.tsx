import { POOL, seasonStartLabel, updatedLabel } from "@/lib/pool"

export function PageHeader({ title, description }: { title: string; description: string }) {
  return (
    <header className="flex flex-col gap-1">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      <p className="text-sm text-muted-foreground">{description}</p>
    </header>
  )
}

export function UpdatedLine() {
  return (
    <p className="text-xs text-muted-foreground">
      Mis à jour le {updatedLabel()}.{" "}
      {!POOL.season_started &&
        `La saison commence le ${seasonStartLabel()}. Tant que les vrais points ne sont pas entrés, le classement est basé sur les projections.`}
    </p>
  )
}
