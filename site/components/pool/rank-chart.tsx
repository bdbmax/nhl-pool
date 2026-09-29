"use client"

import { useState } from "react"
import { Line, LineChart, XAxis, YAxis } from "recharts"

import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { dayLabel, fmt, MANAGERS, POOL } from "@/lib/pool"

// Rang de chaque équipe, matin après matin (data/history). Douze lignes, c'est trop pour douze couleurs :
// les équipes sont en gris fin, et celle qu'on choisit ressort (le meneur par défaut).
const rows = POOL.history.map((h) => ({ date: h.date, ...Object.fromEntries(Object.entries(h.ranks).map(([k, v]) => [`t${k}`, v])) }))
const teams = [...MANAGERS].sort((a, b) => a.rank - b.rank)
const items = teams.map((m) => ({ label: m.name, value: String(m.id) }))
const config = { focus: { label: "Équipe", color: "var(--primary)" } } satisfies ChartConfig

type TipProps = { active?: boolean; label?: string; focus: string }
function Tip({ active, label, focus }: TipProps) {
  if (!active || !label) return null
  const h = POOL.history.find((x) => x.date === label)
  if (!h) return null
  const name = MANAGERS.find((m) => String(m.id) === focus)?.name
  return (
    <div className="rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-xl">
      <div className="font-medium">{dayLabel(label)}</div>
      <div className="text-muted-foreground">
        {name} : {h.ranks[focus]}<sup>e</sup>, {fmt(h.points[focus])} pts
      </div>
    </div>
  )
}

export function RankChart() {
  const [focus, setFocus] = useState(String(teams[0].id))
  return (
    <div className="flex flex-col gap-3">
      <Select items={items} value={focus} onValueChange={(v) => v && setFocus(String(v))}>
        <SelectTrigger aria-label="Équipe en évidence" className="w-full"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {items.map((i) => <SelectItem key={i.value} value={i.value}>{i.label}</SelectItem>)}
          </SelectGroup>
        </SelectContent>
      </Select>
      <ChartContainer config={config} className="aspect-[4/3] w-full sm:aspect-video">
        <LineChart data={rows} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
          <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={32}
            tickFormatter={(d: string) => new Date(`${d}T12:00:00Z`).toLocaleDateString("fr-CA", { day: "numeric", month: "short", timeZone: "UTC" })} />
          <YAxis reversed domain={[1, MANAGERS.length]} ticks={[1, 4, 8, 12]} allowDecimals={false}
            tickLine={false} axisLine={false} width={24} />
          <ChartTooltip cursor content={<Tip focus={focus} />} />
          {teams.filter((m) => String(m.id) !== focus).map((m) => (
            <Line key={m.id} dataKey={`t${m.id}`} type="linear" stroke="var(--muted-foreground)" strokeOpacity={0.3} strokeWidth={1.5}
              dot={false} activeDot={false} isAnimationActive={false} />
          ))}
          <Line dataKey={`t${focus}`} type="linear" stroke="var(--color-focus)" strokeWidth={2.5}
            dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--background)" }} isAnimationActive={false} />
        </LineChart>
      </ChartContainer>
    </div>
  )
}
