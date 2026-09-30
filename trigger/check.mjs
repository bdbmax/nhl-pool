// node trigger/check.mjs: which Toronto slots the half-hourly cron hits, over a summer and a winter day.
import { modeAt, torontoTime } from "./worker.js"
for (const day of ["2026-09-30", "2026-11-01", "2026-12-15", "2027-03-14"]) {
  const hits = []
  for (let m = 0; m < 48 * 60; m += 1) {
    const d = new Date(Date.parse(`${day}T00:00:00Z`) + m * 60000)
    if (d.getUTCMinutes() !== 5 && d.getUTCMinutes() !== 35) continue
    const mode = modeAt(d)
    if (mode && d.toLocaleDateString("en-CA", { timeZone: "America/Toronto" }) === day) hits.push(`${torontoTime(d)} ${mode}`)
  }
  console.log(day, hits.join(", "))
}
