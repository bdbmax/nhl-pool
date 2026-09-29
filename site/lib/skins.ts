// Deux habillages : "default" (Moderne, le site de base en mode clair) et "retro", défini dans
// app/skins.css et appliqué par-dessus avec l'attribut data-skin sur <html>.
export const SKINS = [
  { id: "default", label: "Moderne" },
  { id: "retro", label: "Rétro" },
] as const

export type SkinId = (typeof SKINS)[number]["id"]

export const SKIN_KEY = "pool-skin"

// Runs in <head> before the first paint so a saved skin doesn't flash the default one.
// ?skin=retro in the URL wins and is remembered.
export const SKIN_BOOT = `(function(){try{var q=new URLSearchParams(location.search).get("skin");var s=q||localStorage.getItem("${SKIN_KEY}");if(q)localStorage.setItem("${SKIN_KEY}",q);if(s&&s!=="default")document.documentElement.dataset.skin=s}catch(e){}})()`

export function currentSkin(): SkinId {
  return document.documentElement.dataset.skin === "retro" ? "retro" : "default"
}

export function applySkin(id: SkinId) {
  if (id === "default") delete document.documentElement.dataset.skin
  else document.documentElement.dataset.skin = id
  localStorage.setItem(SKIN_KEY, id)
  const url = new URL(location.href)
  if (url.searchParams.has("skin")) {
    url.searchParams.delete("skin")
    history.replaceState(history.state, "", url)
  }
  window.dispatchEvent(new Event("pool-skin"))
}
