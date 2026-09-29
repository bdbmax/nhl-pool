"use client"

import { useState } from "react"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { countedProjection, fmt, MANAGERS, rosterOf } from "@/lib/pool"

const teams = [...MANAGERS].sort((a, b) => a.slot - b.slot)
const items = teams.map((m) => ({ label: m.name, value: String(m.id) }))

const ROWS: { label: string; value: (id: number) => number }[] = [
  { label: "Points", value: (id) => MANAGERS.find((m) => m.id === id)?.points ?? 0 },
  { label: "Projection", value: (id) => MANAGERS.find((m) => m.id === id)?.expected_total ?? 0 },
  { label: "Attaquants", value: (id) => countedProjection(id, "F") },
  { label: "Défenseurs", value: (id) => countedProjection(id, "D") },
  { label: "Gardien", value: (id) => countedProjection(id, "G") },
  { label: "Blessés", value: (id) => rosterOf(id).filter((p) => p.injury).length },
  { label: "Joueurs du CH", value: (id) => rosterOf(id).filter((p) => p.nhl_team === "MTL").length },
]

function TeamSelect({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <Select items={items} value={value} onValueChange={(v) => v && onChange(String(v))}>
      <SelectTrigger aria-label={label} className="w-full"><SelectValue /></SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {items.map((i) => <SelectItem key={i.value} value={i.value}>{i.label}</SelectItem>)}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}

export function HeadToHead() {
  const [a, setA] = useState(items[0].value)
  const [b, setB] = useState(items[1].value)
  return (
    <Card>
      <CardHeader>
        <CardTitle>Face-à-face</CardTitle>
        <CardDescription>Choisis deux équipes et compare-les ligne par ligne. Les positions montrent les points projetés qui comptent.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <TeamSelect label="Première équipe" value={a} onChange={setA} />
          <TeamSelect label="Deuxième équipe" value={b} onChange={setB} />
        </div>
        <dl className="flex flex-col gap-3 text-sm">
          {ROWS.map((r) => {
            const va = r.value(Number(a)), vb = r.value(Number(b))
            return (
              <div key={r.label} className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 tabular-nums">
                <dd className={va > vb ? "font-semibold" : "text-muted-foreground"}>{fmt(va)}</dd>
                <dt className="text-center text-muted-foreground">{r.label}</dt>
                <dd className={vb > va ? "text-right font-semibold" : "text-right text-muted-foreground"}>{fmt(vb)}</dd>
              </div>
            )
          })}
        </dl>
      </CardContent>
    </Card>
  )
}
