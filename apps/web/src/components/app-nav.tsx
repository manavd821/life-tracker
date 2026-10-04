"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const ITEMS = [
  { href: "/", label: "Today" },
  { href: "/tasks", label: "Tasks", soon: true },
  { href: "/analytics", label: "Analytics", soon: true },
  { href: "/patterns", label: "Patterns", soon: true },
];

const LIBRARY = [
  { href: "/activity-labels", label: "Activity Labels" },
  { href: "/context-tags", label: "Context Tags" },
];

export function AppNav() {
  const pathname = usePathname();

  const linkClass = (active: boolean, disabled = false) =>
    [
      "block rounded-md px-3 py-1.5 text-sm",
      active ? "bg-secondary text-foreground" : "text-muted-foreground",
      disabled ? "cursor-not-allowed opacity-50 hover:bg-transparent" : "hover:bg-secondary/60 hover:text-foreground",
    ].join(" ");

  return (
    <nav className="flex flex-col gap-6">
      <div>
        <p className="px-3 pb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Track
        </p>
        <div className="flex flex-col gap-0.5">
          {ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.soon ? "#" : item.href}
              aria-disabled={item.soon || undefined}
              onClick={(event) => {
                if (item.soon) event.preventDefault();
              }}
              className={linkClass(pathname === item.href, item.soon)}
            >
              <span>{item.label}</span>
              {item.soon ? (
                <span className="ml-2 text-xs text-muted-foreground">soon</span>
              ) : null}
            </Link>
          ))}
        </div>
      </div>

      <div>
        <p className="px-3 pb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
          Library
        </p>
        <div className="flex flex-col gap-0.5">
          {LIBRARY.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={linkClass(pathname.startsWith(item.href))}
            >
              {item.label}
            </Link>
          ))}
        </div>
      </div>
    </nav>
  );
}