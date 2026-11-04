"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import { RecapSummary, TeamDailyRecap } from "@/components/pool/daily-recap"
import { TeamAvatar, TeamCode } from "@/components/pool/team-avatar"
import { dayLabel, MANAGERS, managerById, ord, signed } from "@/lib/pool"
import type { Edition } from "@/lib/recaps"

export function DailyBrowser({ editions }: { editions: Edition[] }) {
  const [date, setDate] = useState(editions[0]?.date ?? "")
  const [team, setTeam] = useState("all")
  const [soiréeDescending, setSoiréeDescending] = useState(true)
  useEffect(() => {
    const p = new URLSearchParams(window.location.search)
    const t = p.get("team"),
      d = p.get("date")
    if (t && MANAGERS.some((m) => String(m.id) === t)) setTeam(t)
    if (d && editions.some((e) => e.date === d)) setDate(d)
  }, [editions])
  function selectTeam(value: string) {
    setTeam(value)
    const url = new URL(window.location.href)
    if (value === "all") url.searchParams.delete("team")
    else url.searchParams.set("team", value)
    url.searchParams.set("date", date)
    window.history.replaceState(null, "", url)
  }
  const edition = editions.find((e) => e.date === date)
  if (!edition)
    return (
      <p className="text-sm text-muted-foreground">
        Le premier bilan sera disponible après deux relevés matinaux.
      </p>
    )
  const selected = edition.teams.find((t) => String(t.id) === team)
  const multi =
    new Date(`${edition.to}T12:00:00Z`).getTime() -
      new Date(`${edition.from}T12:00:00Z`).getTime() >
    86400000
  return (
    <>
      <Link href="/" className="text-xs underline underline-offset-4">
        ← Classement
      </Link>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <span id="daily-date-label" className="text-xs text-muted-foreground">
            Édition
          </span>
          <Select
            value={date}
            onValueChange={(v) => {
              if (v) {
                setDate(v)
                const url = new URL(window.location.href)
                url.searchParams.set("date", v)
                window.history.replaceState(null, "", url)
              }
            }}
          >
            <SelectTrigger
              className="w-full"
              aria-labelledby="daily-date-label"
            >
              <SelectValue>
                {date ? dayLabel(date) : "Choisir une édition"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                {editions.map((e) => (
                  <SelectItem key={e.date} value={e.date}>
                    {dayLabel(e.date)}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1.5">
          <span id="daily-team-label" className="text-xs text-muted-foreground">
            Équipe
          </span>
          <Select value={team} onValueChange={(v) => v && selectTeam(v)}>
            <SelectTrigger
              className="w-full"
              aria-labelledby="daily-team-label"
            >
              <SelectValue>
                {team === "all"
                  ? "Tout le pool"
                  : managerById(Number(team))?.name}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectGroup>
                <SelectItem value="all">Tout le pool</SelectItem>
                {MANAGERS.map((m) => (
                  <SelectItem key={m.id} value={String(m.id)}>
                    {m.name}
                  </SelectItem>
                ))}
              </SelectGroup>
            </SelectContent>
          </Select>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        {multi
          ? `Depuis le relevé couvrant le ${dayLabel(edition.from)}, jusqu’au ${dayLabel(edition.to)}`
          : `Matchs du ${dayLabel(edition.to)}`}{" "}
        · Relevé officiel du {dayLabel(edition.date)}
      </p>
      <div className="flex flex-col gap-6" aria-live="polite">
        {selected ? (
          <>
            <TeamDailyRecap edition={edition} team={selected} full />
            <Link
              href={`/teams/${selected.id}/`}
              className="text-sm underline underline-offset-4"
            >
              Voir la fiche de {managerById(selected.id)?.name} →
            </Link>
          </>
        ) : (
          <>
            <RecapSummary edition={edition} link={false} />
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Équipe</TableHead>
                  <TableHead
                    className="text-right"
                    aria-sort={soiréeDescending ? "descending" : "ascending"}
                  >
                    <button
                      type="button"
                      onClick={() => setSoiréeDescending((v) => !v)}
                      aria-label={
                        soiréeDescending
                          ? "Soirée : trier du plus petit au plus grand"
                          : "Soirée : trier du plus grand au plus petit"
                      }
                    >
                      Soirée {soiréeDescending ? "↓" : "↑"}
                    </button>
                  </TableHead>
                  <TableHead className="text-right">Rang</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {[...edition.teams]
                  .sort(
                    (a, b) =>
                      (soiréeDescending ? b.gain - a.gain : a.gain - b.gain) ||
                      a.rank - b.rank
                  )
                  .map((t) => (
                    <TableRow key={t.id}>
                      <TableCell>
                        <button
                          type="button"
                          className="flex min-w-0 items-center gap-3 text-left"
                          onClick={() => selectTeam(String(t.id))}
                        >
                          <TeamAvatar
                            id={t.id}
                            name={managerById(t.id)?.name ?? ""}
                            size="sm"
                          />
                          <span className="flex min-w-0 items-center">
                            <span className="truncate font-medium">
                              {managerById(t.id)?.name}
                            </span>
                            <TeamCode id={t.id} />
                          </span>
                        </button>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {signed(t.gain)}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {ord(t.previousRank)} → {ord(t.rank)}
                      </TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </>
        )}
      </div>
    </>
  )
}
