import {
  Show,
  SignInButton,
  SignUpButton,
  UserButton,
} from "@clerk/nextjs";
import Link from "next/link";

export default function Home() {
  return (
    <main className="flex flex-1 w-full max-w-3xl flex-col gap-10 px-6 py-24">
      <div className="flex flex-col gap-4">
        <h1 className="text-4xl font-semibold tracking-tight">Life Tracker</h1>
        <p className="text-lg text-zinc-600 dark:text-zinc-400">
          Sign in to track your behaviours, tasks and analytics.
        </p>
      </div>

      <Show
        when="signed-in"
        fallback={
          <div className="flex items-center gap-4">
            <SignInButton mode="modal">
              <button className="rounded-full bg-foreground px-5 py-3 text-background">
                Sign in
              </button>
            </SignInButton>
            <SignUpButton mode="modal">
              <button className="rounded-full border border-solid border-black/[.08] px-5 py-3 dark:border-white/[.145]">
                Sign up
              </button>
            </SignUpButton>
          </div>
        }
      >
        <div className="flex items-center gap-4">
          <Link
            href="/dashboard"
            className="rounded-full bg-foreground px-5 py-3 text-background"
          >
            Go to dashboard
          </Link>
          <UserButton />
        </div>
      </Show>
    </main>
  );
}
