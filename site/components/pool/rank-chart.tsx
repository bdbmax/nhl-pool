"use client"

import { useState } from "react"
import { Line, LineChart, XAxis, YAxis } from "recharts"

import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart"
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TeamMark } from "@/components/pool/team-avatar"
import { dayLabel, fmt, MANAGERS, ord, pct, POOL } from "@/lib/pool"

// Le rang ou les odds de gagner de chaque équipe, matin après matin (data/history). Chaque ligne est à la couleur
// de son équipe (--team-N : son emblème en Moderne, son chandail en Rétro) : les autres, fines et pâles ; celle
// qu'on choisit ressort (le meneur par défaut).
type Metric = "rank" | "odds"
const teams = [...MANAGERS].sort((a, b) => a.rank - b.rank)
const items = teams.map((m) => ({ label: m.name, value: String(m.id) }))
const config = { focus: { label: "Équipe", color: "var(--primary)" } } satisfies ChartConfig
const shortDay = (d: string) =>
  new Date(`${d}T12:00:00Z`).toLocaleDateString("fr-CA", { day: "numeric", month: "short", timeZone: "UTC" })

function rowsFor(metric: Metric) {
  return POOL.history.map((h) => {
    const src = metric === "rank" ? h.ranks : h.win ?? {}
    return { date: h.date, ...Object.fromEntries(Object.entries(src).map(([k, v]) => [`t${k}`, v])) }
  })
}

// Axe des odds : de 0 jusqu'au prochain multiple de 10 au-dessus du plus haut point.
function oddsTop() {
  const top = Math.max(10, ...POOL.history.flatMap((h) => Object.values(h.win ?? {})))
  return Math.ceil(top / 10) * 10
}

function Tip({ active, label, focus }: { active?: boolean; label?: string; focus: string }) {
  if (!active || !label) return null
  const h = POOL.history.find((x) => x.date === label)
  if (!h) return null
  const name = MANAGERS.find((m) => String(m.id) === focus)?.name
  return (
    <div className="rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-xl">
      <div className="font-medium">{dayLabel(label)}</div>
      <div className="text-muted-foreground"><TeamMark id={Number(focus)} /> {name} : {ord(h.ranks[focus])} rang, {fmt(h.points[focus])} pts</div>
      {h.win && <div className="text-muted-foreground">Odds de gagner : {pct(h.win[focus])}</div>}
    </div>
  )
}

function Lines({ metric, focus }: { metric: Metric; focus: string }) {
  const top = oddsTop()
  return (
    <ChartContainer config={config} className="aspect-[4/3] w-full sm:aspect-video">
      <LineChart data={rowsFor(metric)} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={32} tickFormatter={shortDay} />
        {metric === "rank" ? (
          <YAxis reversed domain={[1, MANAGERS.length]} ticks={[1, 4, 8, 12]} allowDecimals={false}
            tickLine={false} axisLine={false} width={24} />
        ) : (
          <YAxis domain={[0, top]} ticks={[0, top / 2, top]} tickFormatter={(v: number) => `${v} %`}
            tickLine={false} axisLine={false} width={40} />
        )}
        <ChartTooltip cursor content={<Tip focus={focus} />} />
        {teams.filter((m) => String(m.id) !== focus).map((m) => (
          <Line key={m.id} dataKey={`t${m.id}`} type="linear" stroke={`var(--team-${m.id})`} strokeOpacity={0.45} strokeWidth={1.5}
            dot={false} activeDot={false} isAnimationActive={false} />
        ))}
        {/* Un contour de la même teinte, plus foncé, fait ressortir la ligne choisie, même quand sa couleur est pâle. */}
        <Line dataKey={`t${focus}`} type="linear" stroke={`color-mix(in oklch, var(--team-${focus}), black 45%)`} strokeWidth={4.5}
          dot={false} activeDot={false} isAnimationActive={false} />
        <Line dataKey={`t${focus}`} type="linear" stroke={`var(--team-${focus})`} strokeWidth={2.5}
          dot={false} activeDot={{ r: 4, strokeWidth: 2, stroke: "var(--background)" }} isAnimationActive={false} />
      </LineChart>
    </ChartContainer>
  )
}

// Page d'accueil : rang ou odds, avec l'équipe en évidence au choix.
export function RankChart() {
  const [focus, setFocus] = useState(String(teams[0].id))
  const [metric, setMetric] = useState<Metric>("rank")
  return (
    <div className="flex flex-col gap-3">
      <Tabs value={metric} onValueChange={(v) => v && setMetric(v as Metric)}>
        <TabsList className="w-full">
          <TabsTrigger value="rank">Rang</TabsTrigger>
          <TabsTrigger value="odds">Odds de gagner</TabsTrigger>
        </TabsList>
      </Tabs>
      <Select items={items} value={focus} onValueChange={(v) => v && setFocus(String(v))}>
        <SelectTrigger aria-label="Équipe en évidence" className="w-full"><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectGroup>
            {items.map((i) => <SelectItem key={i.value} value={i.value}><TeamMark id={Number(i.value)} /> {i.label}</SelectItem>)}
          </SelectGroup>
        </SelectContent>
      </Select>
      <Lines metric={metric} focus={focus} />
    </div>
  )
}

// Page d'équipe : ses odds de gagner, matin après matin, avec les autres équipes en gris derrière.
export function TeamOddsChart({ id }: { id: number }) {
  return <Lines metric="odds" focus={String(id)} />
}
