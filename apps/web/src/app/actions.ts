"use server";

import { revalidatePath } from "next/cache";

import {
  BackendError,
  createActivityLabel,
  createBehavior,
  createContextTag,
  deleteActivityLabel,
  deleteBehavior,
  deleteContextTag,
  updateBehavior,
} from "@/lib/backend";
import type { ActionState } from "@/lib/action-state";

function toState(error: unknown): ActionState {
  if (error instanceof BackendError) {
    return {
      ok: false,
      message: error.message,
      code: error.code,
      conflicts: (error.details.conflicts as string[] | undefined) ?? [],
    };
  }
  return { ok: false, message: "Something went wrong. Please try again." };
}

function values(formData: FormData) {
  const get = (key: string) => {
    const value = formData.get(key);
    return typeof value === "string" ? value : "";
  };
  const optional = (key: string) => {
    const value = get(key);
    return value === "" || value === "none" ? null : value;
  };
  const multi = (key: string) =>
    formData.getAll(key).filter((v): v is string => typeof v === "string" && v !== "");

  return {
    start_date: get("start_date"),
    start_time: get("start_time"),
    end_date: get("end_date"),
    end_time: get("end_time"),
    primary_category: get("primary_category"),
    activity_label_id: optional("activity_label_id"),
    context_tag_ids: multi("context_tag_ids"),
    environment: optional("environment"),
    energy_level: optional("energy_level"),
    emotion_state: optional("emotion_state"),
    focus_state: optional("focus_state"),
    notes: optional("notes"),
    precision: get("precision") || "HIGH",
    behavior_id: get("behavior_id"),
  };
}

function toPayload(raw: ReturnType<typeof values>, startDate: Date) {
  const [startHour, startMinute] = raw.start_time.split(":").map(Number);
  const [endHour, endMinute] = raw.end_time.split(":").map(Number);

  const start = new Date(startDate);
  start.setHours(startHour, startMinute, 0, 0);
  const end = new Date(startDate);
  end.setHours(endHour, endMinute, 0, 0);

  return {
    start_time: start.toISOString(),
    end_time: end.toISOString(),
    primary_category: raw.primary_category,
    activity_label_id: raw.activity_label_id,
    context_tag_ids: raw.context_tag_ids,
    environment: raw.environment,
    energy_level: raw.energy_level,
    emotion_state: raw.emotion_state,
    focus_state: raw.focus_state,
    notes: raw.notes,
    precision: raw.precision,
  };
}

function validate(raw: ReturnType<typeof values>, startDate: Date): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!raw.start_time) errors.start_time = "Start time is required";
  if (!raw.end_time) errors.end_time = "End time is required";
  if (!raw.primary_category) errors.primary_category = "Category is required";
  if (!raw.start_time || !raw.end_time) return errors;

  const [sh, sm] = raw.start_time.split(":").map(Number);
  const [eh, em] = raw.end_time.split(":").map(Number);
  const start = new Date(startDate);
  start.setHours(sh, sm, 0, 0);
  const end = new Date(startDate);
  end.setHours(eh, em, 0, 0);

  if (start >= end) errors.end_time = "End time must be after start time";
  return errors;
}

export async function saveBehavior(
  _prev: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const raw = values(formData);
  const startDate = new Date(`${raw.start_date}T00:00:00`);
  if (Number.isNaN(startDate.getTime())) {
    return { ok: false, fieldErrors: { start_date: "Start date is required" } };
  }

  const fieldErrors = validate(raw, startDate);
  if (Object.keys(fieldErrors).length > 0) return { ok: false, fieldErrors };

  try {
    if (raw.behavior_id) {
      await updateBehavior(raw.behavior_id, toPayload(raw, startDate));
    } else {
      await createBehavior(toPayload(raw, startDate));
    }
    revalidatePath("/");
    return { ok: true };
  } catch (error) {
    return toState(error);
  }
}

export async function removeBehavior(formData: FormData): Promise<void> {
  const id = formData.get("behavior_id");
  if (typeof id !== "string" || id === "") return;
  try {
    await deleteBehavior(id);
    revalidatePath("/");
  } catch (error) {
    console.error(toState(error));
  }
}

export async function addActivityLabel(
  _prev: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const category = formData.get("primary_category");
  const label = formData.get("activity_label");
  if (typeof label !== "string" || label.trim() === "") {
    return { ok: false, fieldErrors: { activity_label: "Label is required" } };
  }
  try {
    await createActivityLabel(String(category), label.trim());
    revalidatePath("/activity-labels");
    return { ok: true };
  } catch (error) {
    return toState(error);
  }
}

export async function removeActivityLabel(formData: FormData): Promise<void> {
  const id = formData.get("activity_label_id");
  if (typeof id !== "string") return;
  try {
    await deleteActivityLabel(id);
    revalidatePath("/activity-labels");
  } catch (error) {
    console.error(toState(error));
  }
}

export async function addContextTag(
  _prev: ActionState,
  formData: FormData,
): Promise<ActionState> {
  const category = formData.get("primary_category");
  const tag = formData.get("context_tag");
  if (typeof tag !== "string" || tag.trim() === "") {
    return { ok: false, fieldErrors: { context_tag: "Tag is required" } };
  }
  try {
    await createContextTag(String(category), tag.trim());
    revalidatePath("/context-tags");
    return { ok: true };
  } catch (error) {
    return toState(error);
  }
}

export async function removeContextTag(formData: FormData): Promise<void> {
  const id = formData.get("behavior_context_tag_id");
  if (typeof id !== "string") return;
  try {
    await deleteContextTag(id);
    revalidatePath("/context-tags");
  } catch (error) {
    console.error(toState(error));
  }
}