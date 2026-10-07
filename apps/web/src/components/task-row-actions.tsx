"use client";

import { useState } from "react";
import { Trash2 } from "lucide-react";

import { removeTask } from "@/app/actions";
import { TaskDialog } from "@/components/task-dialog";
import { Button } from "@/components/ui/button";
import type { ActivityLabel, ContextTag, Task } from "@/lib/backend";

type Props = {
  task: Task;
  labels: ActivityLabel[];
  tags: ContextTag[];
};

export function TaskRowActions({ task, labels, tags }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="flex shrink-0 items-center gap-1">
      <TaskDialog
        task={task}
        labels={labels}
        tags={tags}
        open={open}
        onOpenChange={setOpen}
        trigger={
          <Button variant="ghost" size="sm">
            Edit
          </Button>
        }
      />
      <form action={removeTask}>
        <input type="hidden" name="task_id" value={task.task_id} />
        <Button type="submit" variant="ghost" size="icon-sm" aria-label="Delete task">
          <Trash2 className="size-4 text-muted-foreground" />
        </Button>
      </form>
    </div>
  );
}

export function AddTaskButton({
  labels,
  tags,
  date,
}: {
  labels: ActivityLabel[];
  tags: ContextTag[];
  date: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <TaskDialog
      labels={labels}
      tags={tags}
      date={date}
      open={open}
      onOpenChange={setOpen}
      trigger={<Button size="sm">Add task</Button>}
    />
  );
}