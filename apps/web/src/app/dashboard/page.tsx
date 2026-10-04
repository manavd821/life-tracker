import { UserButton } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";

export default async function DashboardPage() {
  const { userId } = await auth.protect();

  return (
    <main className="flex flex-1 w-full max-w-3xl flex-col gap-6 px-6 py-24">
      <h1 className="text-3xl font-semibold tracking-tight">Dashboard</h1>
      <p className="text-zinc-600 dark:text-zinc-400">
        Clerk user id: <span className="font-mono text-sm">{userId}</span>
      </p>
      <UserButton />
    </main>
  );
}
