"use client";

import { useState } from "react";

import { loadTaskAnalysis } from "@/app/actions";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { Task, TaskAnalysisDetail } from "@/lib/backend";
import { formatClock, formatDuration, formatMinutes, formatRate } from "@/lib/domain";

type Props = {
  task: Task;
  trigger: React.ReactNode;
};

export function TaskDetailDialog({ task, trigger }: Props) {
  const [open, setOpen] = useState(false);
  const [analysis, setAnalysis] = useState<TaskAnalysisDetail | null>(null);
  const [loading, setLoading] = useState(false);

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next || analysis) return;
    setLoading(true);
    void loadTaskAnalysis(task.task_id).then((result) => {
      setAnalysis(result);
      setLoading(false);
    });
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{task.title}</DialogTitle>
          <DialogDescription className="tabular-nums">
            {formatClock(task.start_time)} – {formatClock(task.end_time)} ·{" "}
            {task.primary_category}
            {task.activity_label ? ` · ${task.activity_label.activity_label}` : ""}
          </DialogDescription>
        </DialogHeader>

        {task.description ? (
          <p className="text-sm text-muted-foreground">{task.description}</p>
        ) : null}

        {loading ? (
          <p className="text-sm text-muted-foreground">Loading analysis</p>
        ) : !analysis ? (
          <p role="alert" className="text-sm text-destructive">
            Could not load analysis.
          </p>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-4 rounded-lg border border-border px-4 py-3">
              <Metric label="Planned" value={formatDuration(analysis.planned_minutes)} />
              <Metric label="Effective" value={formatDuration(Math.round(analysis.effective_minutes))} />
              <Metric label="Completion" value={formatRate(analysis.completion_rate)} />
            </div>

            <div className="flex flex-col gap-2">
              <h3 className="text-sm font-medium tracking-wide text-muted-foreground uppercase">
                Contributing behaviors
              </h3>

              {analysis.contributions.length === 0 ? (
                <p className="rounded-lg border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
                  No overlapping behaviors in this window.
                </p>
              ) : (
                analysis.contributions.map((contribution) => (
                  <div
                    key={contribution.behavior_id}
                    className="flex items-start justify-between gap-3 rounded-lg border border-border px-4 py-2 text-sm"
                  >
                    <div className="flex min-w-0 flex-col gap-0.5">
                      <span className="tabular-nums text-muted-foreground">
                        {formatClock(contribution.start_time)} – {formatClock(contribution.end_time)}
                      </span>
                      <span>
                        {contribution.primary_category}
                        {contribution.activity_label ? ` · ${contribution.activity_label}` : ""}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {contribution.overlap_minutes} min overlap · score{" "}
                        {formatMinutes(contribution.match_score)}
                        {contribution.matched_context_tags.length > 0
                          ? ` · + ${contribution.matched_context_tags.map((tag) => `#${tag}`).join(" ")}`
                          : ""}
                      </span>
                    </div>
                    <span className="shrink-0 tabular-nums">
                      {formatMinutes(contribution.effective_minutes)} min
                    </span>
                  </div>
                ))
              )}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs tracking-wide text-muted-foreground uppercase">{label}</span>
      <span className="text-lg font-medium tabular-nums">{value}</span>
    </div>
  );
}

export function TaskDetailButton({ task }: { task: Task }) {
  return (
    <TaskDetailDialog
      task={task}
      trigger={
        <Button variant="ghost" size="sm">
          Details
        </Button>
      }
    />
  );
}