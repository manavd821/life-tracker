import Link from "next/link";

import { getContextPatterns, getTransitionPatterns } from "@/lib/backend";
import {
  formatDuration,
  formatProbability,
  localDateString,
  parseLocalDate,
  shiftDateString,
  timezoneOffsetMinutes,
} from "@/lib/domain";

export default async function PatternsPage({
  searchParams,
}: {
  searchParams: Promise<{ start?: string; end?: string }>;
}) {
  const { start, end } = await searchParams;
  const startDate = start ?? shiftDateString(localDateString(new Date()), -6);
  const endDate = end ?? localDateString(new Date());
  const offset = timezoneOffsetMinutes(parseLocalDate(endDate) ?? new Date());

  const [transitions, context] = await Promise.all([
    getTransitionPatterns(startDate, endDate, offset),
    getContextPatterns(startDate, endDate, offset),
  ]);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Patterns</h1>
          <p className="text-sm text-muted-foreground">
            {startDate} to {endDate}
            <span className="mx-2 text-border">|</span>
            {transitions.window.behavior_count} behaviors
          </p>
        </div>
        <RangeNav startDate={startDate} endDate={endDate} />
      </header>

      <TransitionSection transitions={transitions} />
      <ContextSection context={context} />
    </div>
  );
}

function rangeHref(startDate: string, endDate: string) {
  return `/patterns?start=${startDate}&end=${endDate}`;
}

function RangeNav({ startDate, endDate }: { startDate: string; endDate: string }) {
  const days = Math.round(
    ((parseLocalDate(endDate)?.getTime() ?? 0) - (parseLocalDate(startDate)?.getTime() ?? 0)) /
      86_400_000,
  );

  return (
    <div className="flex flex-wrap items-center gap-1 text-sm">
      <Link
        href={rangeHref(shiftDateString(endDate, -(days + 1)), endDate)}
        className="rounded-md px-2 py-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
      >
        Widen
      </Link>
      <Link
        href={rangeHref(endDate, endDate)}
        className="rounded-md px-2 py-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
      >
        Today
      </Link>
      <Link
        href={rangeHref(shiftDateString(endDate, -6), endDate)}
        className="rounded-md px-2 py-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
      >
        7 days
      </Link>
      <Link
        href={rangeHref(shiftDateString(endDate, -29), endDate)}
        className="rounded-md px-2 py-1 text-muted-foreground hover:bg-secondary hover:text-foreground"
      >
        30 days
      </Link>
    </div>
  );
}

function TransitionSection({
  transitions,
}: {
  transitions: Awaited<ReturnType<typeof getTransitionPatterns>>;
}) {
  const groups = groupBy(
    transitions.category_transitions,
    (row) => row.from_category,
    (row) => ({ label: row.to_category, probability: row.probability, count: row.count }),
  );
  const activity = transitions.activity_transitions;

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
        Behavior Transitions
      </h2>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="flex flex-col gap-2">
          <h3 className="text-xs text-muted-foreground">Category</h3>
          {groups.length === 0 ? (
            <Empty threshold={transitions.minimum_transition_count} unit="transitions" />
          ) : null}
          {groups.map(([from, rows]) => (
            <div key={from} className="flex flex-col gap-1 rounded-lg border border-border px-4 py-3">
              <span className="text-sm font-medium">{from}</span>
              {rows.map((row) => (
                <div key={row.label} className="flex items-center gap-3 pl-3 text-sm">
                  <span className="w-4 shrink-0 text-muted-foreground">↓</span>
                  <span className="flex-1 truncate">{row.label}</span>
                  <span className="w-14 shrink-0 text-right tabular-nums text-muted-foreground">
                    {formatProbability(row.probability)}
                  </span>
                  <span className="w-14 shrink-0 text-right tabular-nums text-muted-foreground">
                    {row.count}×
                  </span>
                </div>
              ))}
            </div>
          ))}
        </div>

        <div className="flex flex-col gap-2">
          <h3 className="text-xs text-muted-foreground">Activity</h3>
          {activity.length === 0 ? (
            <Empty threshold={transitions.minimum_transition_count} unit="transitions" />
          ) : null}
          {activity.map((row) => (
            <div
              key={`${row.from_activity}-${row.to_activity}`}
              className="flex flex-col gap-1 rounded-lg border border-border px-4 py-3 text-sm"
            >
              <div className="flex items-center gap-3">
                <span className="flex-1 truncate">
                  {row.from_category} · {row.from_activity}
                </span>
                <span className="w-14 shrink-0 text-right tabular-nums text-muted-foreground">
                  {formatProbability(row.probability)}
                </span>
                <span className="w-14 shrink-0 text-right tabular-nums text-muted-foreground">
                  {row.count}×
                </span>
              </div>
              <div className="flex items-center gap-3 pl-4">
                <span className="w-4 shrink-0 text-muted-foreground">↓</span>
                <span className="flex-1 truncate">
                  {row.to_category} · {row.to_activity}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ContextSection({ context }: { context: Awaited<ReturnType<typeof getContextPatterns>> }) {
  const stats = groupBy(
    context.context_stats,
    (row) => `${row.dimension} · ${row.category} · ${row.activity_label ?? "No activity label"}`,
    (row) => ({
      label: row.context,
      average: row.average_duration_minutes,
      sessions: row.session_count,
      total: row.total_duration_minutes,
    }),
  );

  return (
    <section className="flex flex-col gap-4">
      <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
        Context Associations
      </h2>

      {context.associations.length > 0 ? (
        <div className="flex flex-col gap-2">
          {context.associations.map((association) => (
            <div
              key={`${association.dimension}-${association.category}-${association.activity_label ?? ""}-${association.context_a}-${association.context_b}`}
              className="flex flex-col gap-1 rounded-lg border border-border px-4 py-3"
            >
              <span className="text-sm font-medium">
                {association.activity_label ?? "No activity label"}
                <span className="ml-2 text-xs text-muted-foreground">
                  {association.dimension}
                </span>
              </span>
              <AssociationRow
                context={association.context_a}
                average={association.average_duration_a}
                sessions={association.sample_a}
              />
              <AssociationRow
                context={association.context_b}
                average={association.average_duration_b}
                sessions={association.sample_b}
              />
              <span className="pl-3 text-xs text-muted-foreground tabular-nums">
                {formatDuration(Math.round(association.difference_minutes))} longer on average
              </span>
            </div>
          ))}
        </div>
      ) : null}

      {stats.length === 0 ? (
        <Empty threshold={context.minimum_context_sessions} unit="sessions" />
      ) : null}

      {stats.map(([group, rows]) => (
        <div key={group} className="flex flex-col gap-1 rounded-lg border border-border px-4 py-3">
          <span className="text-sm font-medium">{group}</span>
          {rows.map((row) => (
            <div
              key={row.label}
              className="flex items-center justify-between gap-3 pl-3 text-sm"
            >
              <span className="truncate text-muted-foreground">{row.label}</span>
              <span className="shrink-0 tabular-nums">
                {formatDuration(Math.round(row.average))} avg
              </span>
              <span className="w-16 shrink-0 text-right tabular-nums text-muted-foreground">
                {row.sessions} sess.
              </span>
            </div>
          ))}
        </div>
      ))}
    </section>
  );
}

function AssociationRow({
  context,
  average,
  sessions,
}: {
  context: string;
  average: number;
  sessions: number;
}) {
  return (
    <div className="flex items-center justify-between gap-3 pl-3 text-sm">
      <span className="truncate">{context}</span>
      <span className="shrink-0 tabular-nums">avg {formatDuration(Math.round(average))}</span>
      <span className="w-16 shrink-0 text-right tabular-nums text-muted-foreground">
        {sessions} sess.
      </span>
    </div>
  );
}

function groupBy<Row, Group extends string, Value>(
  rows: Row[],
  keyOf: (row: Row) => Group,
  valueOf: (row: Row) => Value,
): [Group, Value[]][] {
  const groups = new Map<Group, Value[]>();
  for (const row of rows) {
    const key = keyOf(row);
    const bucket = groups.get(key);
    if (bucket) {
      bucket.push(valueOf(row));
    } else {
      groups.set(key, [valueOf(row)]);
    }
  }
  return [...groups.entries()];
}

function Empty({ threshold, unit }: { threshold: number; unit: string }) {
  return (
    <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
      No pattern yet. At least {threshold} {unit} are needed before one is shown.
    </p>
  );
}
