import type { MetadataRoute } from "next"

// "Ajouter à l'écran d'accueil" : l'icône du patineur (scripts/make_favicon.py) qui ouvre le site
// en plein écran, comme une app.
const base = process.env.NEXT_PUBLIC_BASE_PATH ?? ""

export const dynamic = "force-static"

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Pool LNH 2026-27",
    short_name: "Pool LNH",
    description: "Classement, odds et trophées du pool, mis à jour chaque matin.",
    lang: "fr-CA",
    start_url: `${base}/`,
    scope: `${base}/`,
    display: "standalone",
    background_color: "#1c1b19",
    theme_color: "#1c1b19",
    icons: [
      { src: `${base}/icons/icon-192.png`, sizes: "192x192", type: "image/png", purpose: "any" },
      { src: `${base}/icons/icon-512.png`, sizes: "512x512", type: "image/png", purpose: "any" },
      { src: `${base}/icons/icon-maskable-512.png`, sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  }
}
