"use client";

import { useActionState } from "react";

import { addActivityLabel, removeActivityLabel } from "@/app/actions";
import { idleState } from "@/lib/action-state";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CATEGORIES } from "@/lib/domain";

export function AddActivityLabelForm() {
  const [state, formAction, pending] = useActionState(addActivityLabel, idleState);

  return (
    <form action={formAction} className="flex flex-wrap items-end gap-2">
      <div className="flex flex-col gap-1.5">
        <span className="text-xs text-muted-foreground">Category</span>
        <Select name="primary_category" defaultValue="Study">
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {CATEGORIES.map((category) => (
              <SelectItem key={category} value={category}>
                {category}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-xs text-muted-foreground">Label</span>
        <input
          name="activity_label"
          placeholder="e.g. DSA"
          className="h-9 rounded-md border border-input bg-transparent px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      <Button type="submit" size="sm" disabled={pending}>
        {pending ? "Adding" : "Add"}
      </Button>

      {state.message ? (
        <p className="w-full text-sm text-destructive">{state.message}</p>
      ) : null}
    </form>
  );
}

export function DeleteActivityLabelButton({ id }: { id: string }) {
  return (
    <form action={removeActivityLabel}>
      <input type="hidden" name="activity_label_id" value={id} />
      <Button type="submit" variant="ghost" size="sm" className="text-muted-foreground">
        Remove
      </Button>
    </form>
  );
}