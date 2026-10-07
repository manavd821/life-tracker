"use client";

export default function Loading() {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <div className="h-6 w-32 animate-pulse rounded bg-secondary" />
        <div className="h-4 w-48 animate-pulse rounded bg-secondary" />
      </header>
      <div className="flex flex-col gap-3">
        <div className="h-24 animate-pulse rounded-lg bg-secondary" />
        <div className="h-24 animate-pulse rounded-lg bg-secondary" />
      </div>
      <div className="flex flex-col gap-3">
        <div className="h-24 animate-pulse rounded-lg bg-secondary" />
        <div className="h-24 animate-pulse rounded-lg bg-secondary" />
      </div>
    </div>
  );
}
