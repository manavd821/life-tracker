"use client";

import { useState } from "react";
import { Trash2 } from "lucide-react";

import { removeBehavior } from "@/app/actions";
import { BehaviorDialog } from "@/components/behavior-dialog";
import { Button } from "@/components/ui/button";
import type { ActivityLabel, BehaviorResponse, ContextTag } from "@/lib/backend";

type Props = {
  behavior: BehaviorResponse;
  labels: ActivityLabel[];
  tags: ContextTag[];
};

export function BehaviorRowActions({ behavior, labels, tags }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <div className="flex shrink-0 items-center gap-1">
      <BehaviorDialog
        labels={labels}
        tags={tags}
        behavior={behavior}
        open={open}
        onOpenChange={setOpen}
        trigger={
          <Button variant="ghost" size="sm">
            Edit
          </Button>
        }
      />
      <form action={removeBehavior}>
        <input type="hidden" name="behavior_id" value={behavior.behavior_id} />
        <Button type="submit" variant="ghost" size="icon-sm" aria-label="Delete behavior">
          <Trash2 className="size-4 text-muted-foreground" />
        </Button>
      </form>
    </div>
  );
}