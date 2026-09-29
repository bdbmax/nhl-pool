"use client"

import { Bar, BarChart, XAxis, YAxis } from "recharts"

import { ChartContainer, ChartTooltip, type ChartConfig } from "@/components/ui/chart"
import { dayLabel, fmt, weeklyPoints } from "@/lib/pool"

// Page d'un joueur : ses points semaine par semaine (lundi à lundi), tirés de data/history.
const config = { pts: { label: "Points", color: "var(--primary)" } } satisfies ChartConfig

function Tip({ active, payload }: { active?: boolean; payload?: { payload: { from: string; date: string; pts: number } }[] }) {
  const row = active && payload?.[0]?.payload
  if (!row) return null
  return (
    <div className="rounded-lg border bg-background px-2.5 py-1.5 text-xs shadow-xl">
      <div className="font-medium">Du {dayLabel(row.from)} au {dayLabel(row.date)}</div>
      <div className="text-muted-foreground">{fmt(row.pts)} point{row.pts === 1 ? "" : "s"}</div>
    </div>
  )
}

export function PlayerWeeksChart({ id }: { id: number }) {
  const rows = weeklyPoints(id)
  return (
    <ChartContainer config={config} className="aspect-[2/1] w-full">
      <BarChart data={rows} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
        <XAxis dataKey="date" tickLine={false} axisLine={false} minTickGap={24}
          tickFormatter={(d: string) => new Date(`${d}T12:00:00Z`).toLocaleDateString("fr-CA", { day: "numeric", month: "short", timeZone: "UTC" })} />
        <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={24} />
        <ChartTooltip cursor={{ fill: "var(--muted)" }} content={<Tip />} />
        <Bar dataKey="pts" fill="var(--color-pts)" radius={[4, 4, 0, 0]} maxBarSize={28} isAnimationActive={false} />
      </BarChart>
    </ChartContainer>
  )
}
