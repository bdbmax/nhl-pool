import { dailyEditions } from "@/lib/recaps"
import { PageHeader } from "@/components/pool/page-header"
import { DailyBrowser } from "@/components/pool/daily-browser"

export default function DailyPage() {
  return (
    <>
      <PageHeader
        title="Le quotidien"
        description="Le bilan des matchs terminés, équipe par équipe."
      />
      <DailyBrowser editions={dailyEditions()} />
    </>
  )
}
