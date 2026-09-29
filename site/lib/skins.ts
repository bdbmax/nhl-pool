// Deux habillages : "retro" (par défaut) et "default" (Moderne, le site de base en mode clair). Rétro est
// défini dans app/skins.css et appliqué par-dessus avec l'attribut data-skin sur <html>, déjà présent
// dans le HTML (app/layout.tsx) pour éviter tout éclair de l'habillage Moderne.
export const SKINS = [
  { id: "default", label: "Moderne" },
  { id: "retro", label: "Rétro" },
] as const

export type SkinId = (typeof SKINS)[number]["id"]

export const SKIN_KEY = "pool-skin"
export const DEFAULT_SKIN: SkinId = "retro"

// The choice is kept in a cookie for a year, scoped to the site's path (bdbmax.github.io hosts other sites).
const COOKIE_PATH = `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/`
const COOKIE_ATTRS = `; path=${COOKIE_PATH}; max-age=31536000; SameSite=Lax`

// Runs in <head> before the first paint. Order: ?skin=... in the URL (remembered), the cookie, a choice
// saved by an older version of the site (localStorage, moved to the cookie), else Rétro.
export const SKIN_BOOT = `(function(){try{var k="${SKIN_KEY}",a="${COOKIE_ATTRS}";var q=new URLSearchParams(location.search).get("skin");var m=document.cookie.match(/(?:^|; )${SKIN_KEY}=([^;]*)/);var c=m&&decodeURIComponent(m[1]);var l=null;try{l=localStorage.getItem(k)}catch(e){}var s=q||c||l||"${DEFAULT_SKIN}";if(s!=="retro"&&s!=="default")s="${DEFAULT_SKIN}";if(!c||q)document.cookie=k+"="+s+a;if(s==="default")delete document.documentElement.dataset.skin;else document.documentElement.dataset.skin=s}catch(e){}})()`

export function currentSkin(): SkinId {
  return document.documentElement.dataset.skin === "retro" ? "retro" : "default"
}

export function applySkin(id: SkinId) {
  if (id === "default") delete document.documentElement.dataset.skin
  else document.documentElement.dataset.skin = id
  document.cookie = `${SKIN_KEY}=${id}${COOKIE_ATTRS}`
  const url = new URL(location.href)
  if (url.searchParams.has("skin")) {
    url.searchParams.delete("skin")
    history.replaceState(history.state, "", url)
  }
  window.dispatchEvent(new Event("pool-skin"))
}
