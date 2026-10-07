import Link from "next/link";

import { DateNavigator } from "@/components/date-navigator";
import { getDailyAnalytics } from "@/lib/backend";
import {
  formatDuration,
  formatMinutes,
  formatRate,
  localDateString,
  parseLocalDate,
  timezoneOffsetMinutes,
  weekdayLabel,
} from "@/lib/domain";

export default async function AnalyticsPage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string }>;
}) {
  const { date: requested } = await searchParams;
  const parsed = parseLocalDate(requested);
  const selected = parsed ?? new Date();
  const date = localDateString(selected);
  const offset = timezoneOffsetMinutes(selected);

  const analytics = await getDailyAnalytics(date, offset);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Analytics</h1>
          <p className="text-sm text-muted-foreground">{weekdayLabel(date)}</p>
        </div>
        <DateNavigator date={date} href={(day) => `/analytics?date=${day}`} todayHref="/analytics" />
      </header>

      <section className="flex flex-col gap-3 rounded-lg border border-border px-4 py-3">
        <div className="grid grid-cols-3 gap-4">
          <Stat label="Tracked" value={formatDuration(analytics.summary.tracked_minutes)} />
          <Stat
            label="Unaccounted"
            value={formatDuration(analytics.summary.unaccounted_minutes)}
            muted
          />
          <Stat label="Behaviors" value={String(analytics.summary.behavior_count)} />
        </div>
        <DayCoverage
          tracked={analytics.summary.tracked_minutes}
          dayMinutes={analytics.summary.day_minutes}
        />
      </section>

      {analytics.summary.behavior_count === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          No behaviors recorded for this day.
          <br />
          <Link href={`/?date=${date}`} className="underline underline-offset-4">
            Add your first behavior
          </Link>{" "}
          to start tracking your time.
        </p>
      ) : null}

      <CategorySection analytics={analytics} />
      <ActivitySection analytics={analytics} />
      <TaskSection analytics={analytics} />
    </div>
  );
}

function DayCoverage({ tracked, dayMinutes }: { tracked: number; dayMinutes: number }) {
  const percent = dayMinutes > 0 ? Math.min(100, (tracked / dayMinutes) * 100) : 0;
  return (
    <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
      <div className="h-full bg-foreground" style={{ width: `${percent}%` }} />
    </div>
  );
}

function Stat({ label, value, muted = false }: { label: string; value: string; muted?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs tracking-wide text-muted-foreground uppercase">{label}</span>
      <span className={`text-lg font-medium tabular-nums ${muted ? "text-muted-foreground" : ""}`}>
        {value}
      </span>
    </div>
  );
}

function CategorySection({ analytics }: { analytics: Awaited<ReturnType<typeof getDailyAnalytics>> }) {
  const rows = analytics.categories;
  const largest = rows.reduce((max, row) => Math.max(max, row.duration_minutes), 0);

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
        Time by Category
      </h2>
      {rows.length === 0 ? <Empty /> : null}
      {rows.map((row) => (
        <div key={row.category} className="flex items-center gap-3 text-sm">
          <span className="w-32 shrink-0 truncate">{row.category}</span>
          <span className="h-1 flex-1 overflow-hidden rounded-full bg-muted">
            <span
              className="block h-full bg-foreground"
              style={{ width: `${largest > 0 ? (row.duration_minutes / largest) * 100 : 0}%` }}
            />
          </span>
          <span className="w-20 shrink-0 text-right tabular-nums text-muted-foreground">
            {formatDuration(row.duration_minutes)}
          </span>
        </div>
      ))}
    </section>
  );
}

function ActivitySection({ analytics }: { analytics: Awaited<ReturnType<typeof getDailyAnalytics>> }) {
  const groups = new Map<string, typeof analytics.activities>();
  for (const row of analytics.activities) {
    const bucket = groups.get(row.category);
    if (bucket) {
      bucket.push(row);
    } else {
      groups.set(row.category, [row]);
    }
  }

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
        Activity Breakdown
      </h2>
      {groups.size === 0 ? <Empty /> : null}
      {[...groups.entries()].map(([category, rows]) => (
        <div key={category} className="flex flex-col gap-1 rounded-lg border border-border px-4 py-3">
          <span className="text-sm font-medium">{category}</span>
          {rows.map((row) => (
            <div key={`${row.category}-${row.activity_label ?? "none"}`} className="flex items-center justify-between gap-3 pl-3 text-sm">
              <span className="truncate text-muted-foreground">
                {row.activity_label ?? "No activity label"}
              </span>
              <span className="shrink-0 tabular-nums">{formatDuration(row.duration_minutes)}</span>
            </div>
          ))}
        </div>
      ))}
    </section>
  );
}

function TaskSection({ analytics }: { analytics: Awaited<ReturnType<typeof getDailyAnalytics>> }) {
  const tasks = analytics.tasks;

  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">Tasks</h2>
      {tasks.count === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
          No tasks planned for this day.
        </p>
      ) : (
        <div className="grid grid-cols-4 gap-4 rounded-lg border border-border px-4 py-3">
          <Stat label="Tasks" value={String(tasks.count)} />
          <Stat label="Planned" value={formatDuration(tasks.planned_minutes)} />
          <Stat label="Effective" value={formatDuration(Math.round(tasks.effective_minutes))} />
          <Stat label="Completion" value={formatRate(tasks.completion_rate)} />
        </div>
      )}
      {tasks.count > 0 ? (
        <p className="text-xs text-muted-foreground">
          {formatMinutes(tasks.effective_minutes)} of {tasks.planned_minutes} planned minutes
          counted as effective.
        </p>
      ) : null}
    </section>
  );
}

function Empty() {
  return (
    <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
      Nothing recorded for this day.
    </p>
  );
}