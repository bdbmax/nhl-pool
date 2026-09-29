import type { NextConfig } from "next"

// Static export: the site is plain files, hosted free on GitHub Pages (bdbmax.github.io/nhl-pool).
// BASE_PATH is "/nhl-pool" in the GitHub build (.github/workflows/daily.yml) and empty locally.
const basePath = process.env.BASE_PATH ?? ""

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  basePath,
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
}

export default nextConfig
