"use client";

import { useActionState } from "react";

import { addContextTag, removeContextTag } from "@/app/actions";
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

export function AddContextTagForm() {
  const [state, formAction, pending] = useActionState(addContextTag, idleState);

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
        <span className="text-xs text-muted-foreground">Tag</span>
        <input
          name="context_tag"
          placeholder="e.g. Practice"
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

export function DeleteContextTagButton({ id }: { id: string }) {
  return (
    <form action={removeContextTag}>
      <input type="hidden" name="behavior_context_tag_id" value={id} />
      <Button type="submit" variant="ghost" size="sm" className="text-muted-foreground">
        Remove
      </Button>
    </form>
  );
}