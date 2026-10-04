import { UserButton } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";

import { AppNav } from "@/components/app-nav";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  await auth.protect();

  return (
    <div className="flex min-h-screen w-full">
      <aside className="hidden w-56 shrink-0 flex-col gap-6 border-r border-border px-3 py-6 md:flex">
        <p className="px-3 text-sm font-semibold">Life Tracker</p>
        <AppNav />
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-end gap-3 border-b border-border px-4 py-3 md:hidden">
          <p className="text-sm font-semibold">Life Tracker</p>
          <UserButton />
        </header>

        <div className="flex gap-6 overflow-x-auto border-b border-border px-4 py-2 md:hidden">
          <AppNav />
        </div>

        <main className="flex-1 px-6 py-6">{children}</main>
      </div>
    </div>
  );
}