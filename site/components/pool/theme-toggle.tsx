"use client"

import * as React from "react"
import { Gamepad2Icon, SunIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { applySkin, currentSkin, type SkinId } from "@/lib/skins"

// Bascule entre l'habillage Moderne (par défaut) et Rétro ; le choix reste en mémoire sur l'appareil.
export function ThemeToggle() {
  const [skin, setSkin] = React.useState<SkinId>("default")
  React.useEffect(() => {
    const sync = () => setSkin(currentSkin())
    sync()
    window.addEventListener("pool-skin", sync)
    return () => window.removeEventListener("pool-skin", sync)
  }, [])
  const retro = skin === "retro"
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={retro ? "Passer à l'habillage moderne" : "Passer à l'habillage rétro"}
      title={retro ? "Moderne" : "Rétro"}
      onClick={() => applySkin(retro ? "default" : "retro")}
    >
      {retro ? <SunIcon /> : <Gamepad2Icon />}
    </Button>
  )
}
