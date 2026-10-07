"use client";

import { useActionState, useEffect, useMemo, useState } from "react";

import { saveBehavior } from "@/app/actions";
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
import type { ActivityLabel, BehaviorResponse, ContextTag } from "@/lib/backend";
import {
  CATEGORIES,
  dayKey,
  EMOTION_STATES,
  ENERGY_LEVELS,
  ENVIRONMENTS,
  FOCUS_STATES,
  localDateString,
  PRECISIONS,
  splitIso,
} from "@/lib/domain";

const NONE = "none";

function pad(value: number) {
  return `${value}`.padStart(2, "0");
}

function timeValue(hours: number, minutes: number) {
  return `${pad(hours)}:${pad(minutes)}`;
}

type Props = {
  labels: ActivityLabel[];
  tags: ContextTag[];
  date?: string;
  behavior?: BehaviorResponse;
  trigger: React.ReactNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function BehaviorDialog({
  labels,
  tags,
  date,
  behavior,
  trigger,
  open,
  onOpenChange,
}: Props) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{behavior ? "Edit behavior" : "Add behavior"}</DialogTitle>
          <DialogDescription>
            Times are sent to the server in your local timezone and validated there.
          </DialogDescription>
        </DialogHeader>
        <BehaviorForm
          behavior={behavior}
          date={date}
          labels={labels}
          tags={tags}
          onSaved={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  );
}

function BehaviorForm({
  behavior,
  date,
  labels,
  tags,
  onSaved,
}: {
  behavior?: BehaviorResponse;
  date?: string;
  labels: ActivityLabel[];
  tags: ContextTag[];
  onSaved: () => void;
}) {
  const [state, formAction, pending] = useActionState<ActionState, FormData>(
    saveBehavior,
    idleState,
  );

  const [category, setCategory] = useState(behavior?.primary_category ?? CATEGORIES[0]);
  const [startTime, setStartTime] = useState(() => {
    const parts = behavior ? splitIso(behavior.start_time) : { hours: 9, minutes: 0 };
    return timeValue(parts.hours, parts.minutes);
  });
  const [endTime, setEndTime] = useState(() => {
    const parts = behavior ? splitIso(behavior.end_time) : { hours: 10, minutes: 0 };
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

  const durationMinutes = useMemo(() => {
    const [sh, sm] = startTime.split(":").map(Number);
    const [eh, em] = endTime.split(":").map(Number);
    if (Number.isNaN(sh) || Number.isNaN(eh)) return 0;
    return eh * 60 + em - (sh * 60 + sm);
  }, [startTime, endTime]);

  const invalidRange = durationMinutes <= 0;
  const blockedByServer = [
    "behavior_overlap",
    "activity_label_category_mismatch",
    "context_tag_category_mismatch",
    "activity_label_in_use",
  ].includes(state.code ?? "");
  const canSubmit = !pending && !invalidRange && !blockedByServer;

  return (
    <form action={formAction} className="flex flex-col gap-4">
      {behavior ? <input type="hidden" name="behavior_id" value={behavior.behavior_id} /> : null}
      <input
        type="hidden"
        name="start_date"
        value={behavior ? dayKey(behavior.start_time) : (date ?? localDateString(new Date()))}
      />
      <input type="hidden" name="start_time" value={startTime} />
      <input type="hidden" name="end_time" value={endTime} />

      <div className="grid grid-cols-2 gap-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="start-time">Start</Label>
          <Input
            id="start-time"
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
            type="time"
            value={endTime}
            onChange={(event) => setEndTime(event.target.value)}
            required
          />
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        Duration:{" "}
        <span className={invalidRange ? "text-destructive" : "text-foreground"}>
          {invalidRange
            ? "end must be after start"
            : `${Math.floor(durationMinutes / 60)}h ${durationMinutes % 60}m`}
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
          defaultValue={behavior?.activity_label?.activity_label_id ?? NONE}
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
                    behavior?.context_tags.some(
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

      <div className="grid grid-cols-2 gap-3">
        <SelectField name="environment" label="Environment" options={ENVIRONMENTS} />
        <SelectField name="energy_level" label="Energy" options={ENERGY_LEVELS} />
        <SelectField name="emotion_state" label="Emotion" options={EMOTION_STATES} />
        <SelectField name="focus_state" label="Focus" options={FOCUS_STATES} />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="notes">Notes</Label>
        <Textarea
          id="notes"
          name="notes"
          rows={2}
          defaultValue={behavior?.notes ?? ""}
          placeholder="Optional"
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label>Precision</Label>
        <div className="flex gap-4">
          {PRECISIONS.map((precision) => (
            <label key={precision} className="flex items-center gap-1.5 text-sm">
              <input
                type="radio"
                name="precision"
                value={precision}
                defaultChecked={(behavior?.precision ?? "HIGH") === precision}
                className="size-4 accent-foreground"
              />
              {precision === "HIGH" ? "High" : "Low"}
            </label>
          ))}
        </div>
      </div>

      {state.message ? (
        <div
          role="alert"
          className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm"
        >
          <p className="font-medium">{state.message}</p>
          {state.code === "behavior_overlap" ? (
            <>
              {state.conflicts?.length ? (
                <ul className="mt-1 list-disc pl-4 text-muted-foreground">
                  {state.conflicts.map((conflict) => (
                    <li key={conflict}>{conflict}</li>
                  ))}
                </ul>
              ) : null}
              <p className="mt-1 text-muted-foreground">Adjust the time range before saving.</p>
            </>
          ) : null}
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

function SelectField({
  name,
  label,
  options,
}: {
  name: string;
  label: string;
  options: readonly string[];
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      <Select name={name} defaultValue={NONE}>
        <SelectTrigger className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={NONE}>None</SelectItem>
          {options.map((option) => (
            <SelectItem key={option} value={option}>
              {option}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}