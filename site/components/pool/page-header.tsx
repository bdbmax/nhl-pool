import { POOL, seasonStartLabel, updatedLabel } from "@/lib/pool"

export function PageHeader({ title, description }: { title: string; description?: string }) {
  return (
    <header className="flex flex-col gap-1">
      <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
    </header>
  )
}

export function UpdatedLine() {
  return (
    <p className="text-xs text-muted-foreground">
      Mis à jour le {updatedLabel()}
      {POOL.update === "evening" && " · matchs du soir inclus"}
      {!POOL.season_started && ` · selon les projections jusqu'au ${seasonStartLabel()}`}
    </p>
  )
}
