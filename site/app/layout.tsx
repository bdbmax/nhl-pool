import type { Metadata, Viewport } from "next"
import { Geist, Geist_Mono, Silkscreen } from "next/font/google"

import "./globals.css"
import "./skins.css"
import { BottomNav, TopNav } from "@/components/pool/nav"
import { ThemeToggle } from "@/components/pool/theme-toggle"
import { ThemeProvider } from "@/components/theme-provider"
import { skaterStyle, standingsOrder } from "@/lib/jerseys"
import { SKIN_BOOT } from "@/lib/skins"
import { cn } from "@/lib/utils"

const geist = Geist({ subsets: ["latin"], variable: "--font-sans" })
const fontMono = Geist_Mono({ subsets: ["latin"], variable: "--font-mono" })

// Police de l'habillage rétro (app/skins.css), l'habillage par défaut : préchargée.
const pixelFont = Silkscreen({ weight: ["400", "700"], subsets: ["latin"], variable: "--font-pixel" })

const description = "Insert coin. 12 golfeurs, 1 jupe & 1 collant"

// Aperçu des liens partagés (Messenger, iMessage…) : public/share.jpg, généré par scripts/make_share.py.
export const metadata: Metadata = {
  metadataBase: new URL("https://nhlpool.ca"),
  title: "Pool 2026-27",
  description,
  openGraph: {
    type: "website",
    locale: "fr_CA",
    siteName: "Pool 2026-27",
    title: "Pool 2026-27",
    description,
    images: [{ url: `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/share.jpg`, width: 1200, height: 630, alt: "Pool 2026-27 : les chandails des 12 équipes" }],
  },
  twitter: { card: "summary_large_image" },
  // Ouvert depuis l'écran d'accueil de l'iPhone : plein écran, avec ce nom sous l'icône (app/apple-icon.png).
  appleWebApp: { capable: true, title: "Pool LNH", statusBarStyle: "black" },
  other: { "apple-mobile-web-app-capable": "yes" }, // older iPhones (newer ones read app/manifest.ts)
}

export const viewport: Viewport = {
  width: "device-width", initialScale: 1, viewportFit: "cover", themeColor: "#1c1b19",
}

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="fr-CA"
      data-skin="retro"
      suppressHydrationWarning
      className={cn("antialiased", fontMono.variable, "font-sans", geist.variable, pixelFont.variable)}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: SKIN_BOOT }} />
        {/* Rétro : le meneur remonte la glace, le 2e la descend. Une page d'équipe met l'équipe à la place du meneur. */}
        <style dangerouslySetInnerHTML={{ __html: skaterStyle(standingsOrder()[0].id, standingsOrder()[1].id) }} />
      </head>
      <body>
        <ThemeProvider>
          <div className="flex min-h-svh flex-col">
            <header data-slot="site-header" className="sticky top-0 z-20 border-b bg-background">
              <div className="mx-auto flex h-14 w-full max-w-3xl items-center justify-between px-4">
                <span data-slot="brand" className="font-semibold tracking-tight">Pool 2026-27</span>
                <div className="flex items-center gap-1">
                  <TopNav />
                  <ThemeToggle />
                </div>
              </div>
            </header>
            <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 px-4 pt-6 pb-24 md:pb-10">
              {children}
            </main>
            <BottomNav />
          </div>
        </ThemeProvider>
      </body>
    </html>
  )
}
