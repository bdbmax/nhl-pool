import type { NextConfig } from "next"

// Static export: the site is plain files, hosted free on GitHub Pages at https://nhlpool.ca (the domain's
// DNS is on Cloudflare, "DNS only"). Served at the domain root, so BASE_PATH is empty; set it only to host
// the site under a sub-path (it was "/nhl-pool" on bdbmax.github.io/nhl-pool).
const basePath = process.env.BASE_PATH ?? ""

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  basePath,
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
}

export default nextConfig
