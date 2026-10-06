"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";

export default function AnalyticsError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-6">
      <h1 className="text-base font-medium">Could not load analytics</h1>
      <p className="text-sm text-muted-foreground">
        The request to the analytics service failed. This usually means the backend is not
        reachable or rejected the request.
      </p>
      <Button variant="outline" size="sm" onClick={reset}>
        Try again
      </Button>
    </div>
  );
}