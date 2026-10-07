import { AddBehaviorButton } from "@/components/add-behavior-button";
import { BehaviorRowActions } from "@/components/behavior-row-actions";
import { DateNavigator } from "@/components/date-navigator";
import { getActivityLabels, getContextTags, getTimeline } from "@/lib/backend";
import {
  formatClock,
  formatDuration,
  localDateString,
  parseLocalDate,
  timezoneOffsetMinutes,
  weekdayLabel,
} from "@/lib/domain";

type Timeline = Awaited<ReturnType<typeof getTimeline>>;

function interleave(timeline: Timeline) {
  const items: (
    | { kind: "behavior"; key: string; behavior: Timeline["behaviors"][number] }
    | { kind: "gap"; key: string; start: string; end: string; minutes: number }
  )[] = [
    ...timeline.behaviors.map((behavior) => ({
      kind: "behavior" as const,
      key: behavior.behavior_id,
      behavior,
    })),
    ...timeline.unaccounted.map((gap) => ({
      kind: "gap" as const,
      key: `gap-${gap.start_time}`,
      start: gap.start_time,
      end: gap.end_time,
      minutes: gap.duration_minutes,
    })),
  ];

  return items.sort(
    (a, b) =>
      new Date(a.kind === "gap" ? a.start : a.behavior.start_time).getTime() -
      new Date(b.kind === "gap" ? b.start : b.behavior.start_time).getTime(),
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

export default async function BehaviorsPage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string }>;
}) {
  const { date: requested } = await searchParams;
  const selected = parseLocalDate(requested) ?? new Date();
  const date = localDateString(selected);
  const offset = timezoneOffsetMinutes(selected);

  const [timeline, labels, tags] = await Promise.all([
    getTimeline(date, offset),
    getActivityLabels(),
    getContextTags(),
  ]);

  const items = interleave(timeline);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Behaviors</h1>
          <p className="text-sm text-muted-foreground">{weekdayLabel(date)}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <DateNavigator date={date} href={(day) => `/?date=${day}`} todayHref="/" />
          <AddBehaviorButton labels={labels} tags={tags} date={date} />
        </div>
      </header>

      <section className="grid grid-cols-3 gap-4 rounded-lg border border-border px-4 py-3">
        <Stat label="Tracked" value={formatDuration(timeline.total_tracked_minutes)} />
        <Stat
          label="Unaccounted"
          value={formatDuration(timeline.total_unaccounted_minutes)}
          muted
        />
        <Stat label="Behaviors" value={String(timeline.total_behaviors)} />
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
          Timeline
        </h2>

        {items.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
            No behaviors recorded for this day.
          </p>
        ) : null}

        {items.map((item) =>
          item.kind === "gap" ? (
            <GapRow key={item.key} start={item.start} end={item.end} minutes={item.minutes} />
          ) : (
            <BehaviorRow
              key={item.key}
              behavior={item.behavior}
              labels={labels}
              tags={tags}
            />
          ),
        )}
      </section>
    </div>
  );
}

function BehaviorRow({
  behavior,
  labels,
  tags,
}: {
  behavior: Timeline["behaviors"][number];
  labels: Awaited<ReturnType<typeof getActivityLabels>>;
  tags: Awaited<ReturnType<typeof getContextTags>>;
}) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-border px-4 py-3">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex items-center gap-2 text-sm tabular-nums text-muted-foreground">
          <span>
            {formatClock(behavior.start_time)} – {formatClock(behavior.end_time)}
          </span>
          <span className="text-xs">({formatDuration(behavior.duration_minutes)})</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-medium">{behavior.primary_category}</span>
          {behavior.activity_label ? (
            <span className="text-sm text-muted-foreground">
              {behavior.activity_label.activity_label}
            </span>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
          {behavior.environment ? <span>{behavior.environment}</span> : null}
          {behavior.focus_state ? <span>{behavior.focus_state}</span> : null}
          {behavior.energy_level ? <span>{behavior.energy_level}</span> : null}
          {behavior.emotion_state ? <span>{behavior.emotion_state}</span> : null}
          {behavior.context_tags.map((tag) => (
            <span key={tag.behavior_context_tag_id}>#{tag.context_tag}</span>
          ))}
        </div>
      </div>
      <BehaviorRowActions behavior={behavior} labels={labels} tags={tags} />
    </div>
  );
}

function GapRow({ start, end, minutes }: { start: string; end: string; minutes: number }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-dashed border-border bg-muted/30 px-4 py-2 text-sm text-muted-foreground">
      <span className="tabular-nums">
        {formatClock(start)} – {formatClock(end)}
      </span>
      <span className="tracking-wide uppercase">Unaccounted</span>
      <span className="tabular-nums">{formatDuration(minutes)}</span>
    </div>
  );
}