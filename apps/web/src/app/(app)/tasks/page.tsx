import { AddTaskButton, TaskRowActions } from "@/components/task-row-actions";
import { TaskDetailButton } from "@/components/task-detail-dialog";
import {
  getActivityLabels,
  getContextTags,
  getTaskAnalysisAll,
  getTasks,
  type TaskAnalysis,
} from "@/lib/backend";
import {
  dayKey,
  dayLabel,
  formatClock,
  formatDuration,
  formatMinutes,
  formatRate,
} from "@/lib/domain";

function groupByDay<T extends { start_time: string }>(items: T[]) {
  const groups = new Map<string, T[]>();
  for (const item of items) {
    const key = dayKey(item.start_time);
    const bucket = groups.get(key);
    if (bucket) {
      bucket.push(item);
    } else {
      groups.set(key, [item]);
    }
  }
  return [...groups.entries()];
}

function plannedTotal(analyses: TaskAnalysis[]): number {
  return analyses.reduce((total, analysis) => total + analysis.planned_minutes, 0);
}

function effectiveTotal(analyses: TaskAnalysis[]): number {
  return analyses.reduce((total, analysis) => total + analysis.effective_minutes, 0);
}

export default async function TasksPage() {
  const [tasks, analyses, labels, tags] = await Promise.all([
    getTasks(),
    getTaskAnalysisAll(),
    getActivityLabels(),
    getContextTags(),
  ]);

  const analysisById = new Map(analyses.map((analysis) => [analysis.task_id, analysis]));
  const planned = plannedTotal(analyses);
  const effective = effectiveTotal(analyses);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Tasks</h1>
          <p className="text-sm text-muted-foreground">
            {planned > 0
              ? `${formatDuration(Math.round(effective))} effective of ${formatDuration(planned)} planned`
              : "Plan what you intend to do."}
          </p>
        </div>
        <AddTaskButton labels={labels} tags={tags} />
      </header>

      {tasks.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
          No tasks yet. Add the first one.
        </p>
      ) : null}

      {groupByDay(tasks).map(([key, dayTasks]) => (
        <section key={key} className="flex flex-col gap-2">
          <h2 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
            {dayLabel(dayTasks[0].start_time)}
          </h2>
          {dayTasks.map((task) => (
            <TaskRow
              key={task.task_id}
              task={task}
              analysis={analysisById.get(task.task_id)}
              labels={labels}
              tags={tags}
            />
          ))}
        </section>
      ))}
    </div>
  );
}

function TaskRow({
  task,
  analysis,
  labels,
  tags,
}: {
  task: Awaited<ReturnType<typeof getTasks>>[number];
  analysis: TaskAnalysis | undefined;
  labels: Awaited<ReturnType<typeof getActivityLabels>>;
  tags: Awaited<ReturnType<typeof getContextTags>>;
}) {
  const rate = analysis?.completion_rate ?? 0;

  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-border px-4 py-3">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex items-center gap-2 text-sm tabular-nums text-muted-foreground">
          <span>
            {formatClock(task.start_time)} – {formatClock(task.end_time)}
          </span>
          <span className="text-xs">({formatDuration(task.planned_minutes)})</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-medium">{task.title}</span>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>
            {task.primary_category}
            {task.activity_label ? ` · ${task.activity_label.activity_label}` : ""}
          </span>
          {task.context_tags.map((tag) => (
            <span key={tag.behavior_context_tag_id}>#{tag.context_tag}</span>
          ))}
        </div>
        <div className="mt-1 flex items-center gap-2">
          <span className="w-12 text-sm tabular-nums">{formatRate(rate)}</span>
          <span className="h-1 w-24 overflow-hidden rounded-full bg-secondary">
            <span
              className="block h-full bg-foreground"
              style={{ width: `${Math.min(100, Math.max(0, rate))}%` }}
            />
          </span>
          <span className="text-xs tabular-nums text-muted-foreground">
            {formatMinutes(analysis?.effective_minutes ?? 0)} / {analysis?.planned_minutes ?? 0} min
          </span>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <TaskDetailButton task={task} />
        <TaskRowActions task={task} labels={labels} tags={tags} />
      </div>
    </div>
  );
}