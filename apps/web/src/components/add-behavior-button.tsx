"use client";

import { useState } from "react";
import { Plus } from "lucide-react";

import { BehaviorDialog } from "@/components/behavior-dialog";
import { Button } from "@/components/ui/button";
import type { ActivityLabel, ContextTag } from "@/lib/backend";

type Props = {
  labels: ActivityLabel[];
  tags: ContextTag[];
  date: string;
};

export function AddBehaviorButton({ labels, tags, date }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <BehaviorDialog
      labels={labels}
      tags={tags}
      date={date}
      open={open}
      onOpenChange={setOpen}
      trigger={
        <Button size="sm">
          <Plus className="size-4" />
          Add behavior
        </Button>
      }
    />
  );
}