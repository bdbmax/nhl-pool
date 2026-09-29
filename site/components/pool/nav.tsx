"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { AwardIcon, ListOrderedIcon, StarIcon, TrophyIcon, UsersIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { NAV } from "@/lib/pool"
import { cn } from "@/lib/utils"

const ICONS = { trophy: TrophyIcon, users: UsersIcon, list: ListOrderedIcon, star: StarIcon, award: AwardIcon }

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname.startsWith(href)
}

// Bottom tab bar on phones, a top bar from the md breakpoint up.
export function BottomNav() {
  const pathname = usePathname()
  return (
    <nav
      aria-label="Navigation principale"
      data-slot="bottom-nav"
      className="fixed inset-x-0 bottom-0 z-20 border-t bg-background pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      <ul className="mx-auto grid max-w-md grid-cols-5">
        {NAV.map((item) => {
          const Icon = ICONS[item.icon]
          const active = isActive(pathname, item.href)
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex h-16 flex-col items-center justify-center gap-1 text-xs text-muted-foreground",
                  active && "text-foreground"
                )}
              >
                <Icon aria-hidden className="size-5" />
                {item.label}
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

export function TopNav() {
  const pathname = usePathname()
  return (
    <nav aria-label="Navigation principale" className="hidden items-center gap-1 md:flex">
      {NAV.map((item) => (
        <Button
          key={item.href}
          variant={isActive(pathname, item.href) ? "secondary" : "ghost"}
          size="sm"
          render={<Link href={item.href} />}
          nativeButton={false}
        >
          {item.label}
        </Button>
      ))}
    </nav>
  )
}
