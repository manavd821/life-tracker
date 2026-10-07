import Link from "next/link";
import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { fullDateLabel, localDateString, shiftDateString } from "@/lib/domain";

type Props = {
  date: string;
  href: (date: string) => string;
  todayHref?: string;
};

export function DateNavigator({ date, href, todayHref }: Props) {
  const today = localDateString(new Date());
  const isToday = date === today;
  const canGoNext = date < today;

  return (
    <div className="flex flex-wrap items-center justify-end gap-1">
      <Button asChild variant="outline" size="sm">
        <Link href={href(shiftDateString(date, -1))}>
          <ChevronLeft className="size-4" />
          <span className="hidden sm:inline">Previous Day</span>
        </Link>
      </Button>

      <span className="min-w-36 text-center text-sm font-medium tabular-nums">
        {fullDateLabel(date)}
      </span>

      {canGoNext ? (
        <Button asChild variant="outline" size="sm">
          <Link href={href(shiftDateString(date, 1))}>
            <span className="hidden sm:inline">Next Day</span>
            <ChevronRight className="size-4" />
          </Link>
        </Button>
      ) : (
        <Button variant="outline" size="sm" disabled aria-label="Next day">
          <span className="hidden sm:inline">Next Day</span>
          <ChevronRight className="size-4" />
        </Button>
      )}

      {!isToday && todayHref ? (
        <Button asChild variant="ghost" size="sm">
          <Link href={todayHref}>Today</Link>
        </Button>
      ) : null}
    </div>
  );
}
