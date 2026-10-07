"use client";

import { useActionState, useEffect, useMemo, useState } from "react";

import { saveTask } from "@/app/actions";
import { idleState, type ActionState } from "@/lib/action-state";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import type { ActivityLabel, ContextTag, Task } from "@/lib/backend";
import { CATEGORIES, localDateString, splitIso } from "@/lib/domain";

const NONE = "none";

function pad(value: number) {
  return `${value}`.padStart(2, "0");
}

function timeValue(hours: number, minutes: number) {
  return `${pad(hours)}:${pad(minutes)}`;
}

function dateValue(iso: string) {
  return localDateString(new Date(iso));
}

type Props = {
  labels: ActivityLabel[];
  tags: ContextTag[];
  date?: string;
  task?: Task;
  trigger: React.ReactNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function TaskDialog({ labels, tags, date, task, trigger, open, onOpenChange }: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{task ? "Edit task" : "Add task"}</DialogTitle>
          <DialogDescription>
            Planned time. Completion is calculated by the server from recorded behaviors.
          </DialogDescription>
        </DialogHeader>
        <TaskForm
          task={task}
          date={date}
          labels={labels}
          tags={tags}
          onSaved={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  );
}

function TaskForm({
  task,
  date,
  labels,
  tags,
  onSaved,
}: {
  task?: Task;
  date?: string;
  labels: ActivityLabel[];
  tags: ContextTag[];
  onSaved: () => void;
}) {
  const [state, formAction, pending] = useActionState<ActionState, FormData>(saveTask, idleState);

  const defaultDate = date ?? localDateString(new Date());
  const [category, setCategory] = useState(task?.primary_category ?? CATEGORIES[1]);
  const [startDate, setStartDate] = useState(() => (task ? dateValue(task.start_time) : defaultDate));
  const [endDate, setEndDate] = useState(() =>
    task ? dateValue(task.end_time) : defaultDate,
  );
  const [startTime, setStartTime] = useState(() => {
    const parts = task ? splitIso(task.start_time) : { hours: 9, minutes: 0 };
    return timeValue(parts.hours, parts.minutes);
  });
  const [endTime, setEndTime] = useState(() => {
    const parts = task ? splitIso(task.end_time) : { hours: 12, minutes: 0 };
    return timeValue(parts.hours, parts.minutes);
  });

  useEffect(() => {
    if (state.ok) onSaved();
  }, [state.ok, onSaved]);

  const categoryLabels = useMemo(
    () => labels.filter((label) => label.primary_category === category),
    [labels, category],
  );
  const categoryTags = useMemo(
    () => tags.filter((tag) => tag.primary_category === category),
    [tags, category],
  );

  const plannedMinutes = useMemo(() => {
    const start = new Date(`${startDate}T${startTime}`);
    const end = new Date(`${endDate}T${endTime}`);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 0;
    return Math.round((end.getTime() - start.getTime()) / 60000);
  }, [startDate, startTime, endDate, endTime]);

  const invalidRange = plannedMinutes <= 0;
  const blockedByServer = ["activity_label_category_mismatch", "context_tag_category_mismatch"].includes(
    state.code ?? "",
  );
  const canSubmit = !pending && !invalidRange && !blockedByServer;

  return (
    <form action={formAction} className="flex flex-col gap-4">
      {task ? <input type="hidden" name="task_id" value={task.task_id} /> : null}

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="title">Title</Label>
        <Input
          id="title"
          name="title"
          defaultValue={task?.title ?? ""}
          placeholder="DSA Preparation"
          required
        />
      </div>

      <div className="grid grid-cols-4 gap-3">
        <div className="col-span-2 flex flex-col gap-1.5">
          <Label htmlFor="start-date">Start date</Label>
          <Input
            id="start-date"
            name="start_date"
            type="date"
            value={startDate}
            onChange={(event) => setStartDate(event.target.value)}
            required
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="start-time">Start</Label>
          <Input
            id="start-time"
            name="start_time"
            type="time"
            value={startTime}
            onChange={(event) => setStartTime(event.target.value)}
            required
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="end-time">End</Label>
          <Input
            id="end-time"
            name="end_time"
            type="time"
            value={endTime}
            onChange={(event) => setEndTime(event.target.value)}
            required
          />
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="end-date">End date</Label>
        <Input
          id="end-date"
          name="end_date"
          type="date"
          value={endDate}
          onChange={(event) => setEndDate(event.target.value)}
          required
        />
      </div>

      <p className="text-sm text-muted-foreground">
        Planned{" "}
        <span className={invalidRange ? "text-destructive" : "text-foreground"}>
          {invalidRange ? "end must be after start" : `${plannedMinutes} min`}
        </span>
      </p>

      <div className="flex flex-col gap-1.5">
        <Label>Category</Label>
        <Select name="primary_category" value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CATEGORIES.map((item) => (
              <SelectItem key={item} value={item}>
                {item}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label>Activity label</Label>
        <Select
          name="activity_label_id"
          defaultValue={task?.activity_label?.activity_label_id ?? NONE}
          key={category}
        >
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={NONE}>None</SelectItem>
            {categoryLabels.map((label) => (
              <SelectItem key={label.activity_label_id} value={label.activity_label_id}>
                {label.activity_label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {categoryTags.length > 0 ? (
        <fieldset className="flex flex-col gap-2">
          <legend className="text-sm font-medium">Context tags</legend>
          <div className="flex flex-wrap gap-3">
            {categoryTags.map((tag) => (
              <label key={tag.behavior_context_tag_id} className="flex items-center gap-1.5 text-sm">
                <input
                  type="checkbox"
                  name="context_tag_ids"
                  value={tag.behavior_context_tag_id}
                  defaultChecked={
                    task?.context_tags.some(
                      (t) => t.behavior_context_tag_id === tag.behavior_context_tag_id,
                    ) ?? false
                  }
                  className="size-4 accent-foreground"
                />
                {tag.context_tag}
              </label>
            ))}
          </div>
        </fieldset>
      ) : null}

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="description">Description</Label>
        <Textarea
          id="description"
          name="description"
          rows={2}
          defaultValue={task?.description ?? ""}
          placeholder="Optional"
        />
      </div>

      {state.message ? (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm"
        >
          {state.message}
        </div>
      ) : null}
      {state.fieldErrors ? (
        <div role="alert" className="text-sm text-destructive">
          {Object.values(state.fieldErrors).join(", ")}
        </div>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button type="submit" disabled={!canSubmit}>
          {pending ? "Saving" : "Save"}
        </Button>
      </div>
    </form>
  );
}