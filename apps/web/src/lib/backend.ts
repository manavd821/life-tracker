import "server-only";

import { auth } from "@clerk/nextjs/server";

const BACKEND_URL = process.env.BACKEND_API_URL ?? "http://127.0.0.1:8000";

export class BackendError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
  }
}

export type Timeline = {
  date: string;
  behaviors: BehaviorResponse[];
  unaccounted: {
    start_time: string;
    end_time: string;
    duration_minutes: number;
  }[];
  total_tracked_minutes: number;
  total_unaccounted_minutes: number;
  total_behaviors: number;
};

export type BehaviorResponse = {
  behavior_id: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  primary_category: string;
  activity_label: { activity_label_id: string; primary_category: string; activity_label: string } | null;
  energy_level: string | null;
  emotion_state: string | null;
  focus_state: string | null;
  environment: string | null;
  precision: string;
  source: string;
  notes: string | null;
  context_tags: { behavior_context_tag_id: string; primary_category: string; context_tag: string }[];
};

export type ActivityLabel = {
  activity_label_id: string;
  primary_category: string;
  activity_label: string;
};

export type ContextTag = {
  behavior_context_tag_id: string;
  primary_category: string;
  context_tag: string;
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { getToken } = await auth();
  const token = await getToken();

  const response = await fetch(`${BACKEND_URL}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });

  if (!response.ok) {
    let code = "backend_error";
    let message = `Request failed with status ${response.status}`;
    let details: Record<string, unknown> = {};
    try {
      const body = await response.json();
      const error: Record<string, unknown> = body.error ?? {};
      code = (error.code as string) ?? code;
      message = (error.message as string) ?? message;
      details = { ...error };
      delete details.code;
      delete details.message;
    } catch {
      // non-JSON error body
    }
    throw new BackendError(response.status, code, message, details);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const getTimeline = (date: string, tzOffsetMinutes: number) =>
  request<Timeline>(
    `/api/behaviors?date=${date}&tz_offset_minutes=${tzOffsetMinutes}`,
  );

export const createBehavior = (body: Record<string, unknown>) =>
  request<BehaviorResponse>("/api/behaviors", {
    method: "POST",
    body: JSON.stringify(body),
  });

export const updateBehavior = (behaviorId: string, body: Record<string, unknown>) =>
  request<BehaviorResponse>(`/api/behaviors/${behaviorId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });

export const deleteBehavior = (behaviorId: string) =>
  request<void>(`/api/behaviors/${behaviorId}`, { method: "DELETE" });

export const getActivityLabels = () => request<ActivityLabel[]>("/api/activity-labels");

export const createActivityLabel = (primaryCategory: string, activityLabel: string) =>
  request<ActivityLabel>("/api/activity-labels", {
    method: "POST",
    body: JSON.stringify({ primary_category: primaryCategory, activity_label: activityLabel }),
  });

export const deleteActivityLabel = (id: string) =>
  request<void>(`/api/activity-labels/${id}`, { method: "DELETE" });

export const getContextTags = () => request<ContextTag[]>("/api/context-tags");

export const createContextTag = (primaryCategory: string, contextTag: string) =>
  request<ContextTag>("/api/context-tags", {
    method: "POST",
    body: JSON.stringify({ primary_category: primaryCategory, context_tag: contextTag }),
  });

export const deleteContextTag = (id: string) =>
  request<void>(`/api/context-tags/${id}`, { method: "DELETE" });