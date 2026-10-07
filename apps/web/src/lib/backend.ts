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

export type Task = {
  task_id: string;
  user_id: string;
  title: string;
  primary_category: string;
  activity_label: ActivityLabel | null;
  context_tags: ContextTag[];
  start_time: string;
  end_time: string;
  planned_minutes: number;
  description: string | null;
  created_at: string;
  updated_at: string;
};

export type TaskAnalysis = {
  task_id: string;
  planned_minutes: number;
  effective_minutes: number;
  completion_rate: number;
};

export type BehaviorContribution = {
  behavior_id: string;
  start_time: string;
  end_time: string;
  primary_category: string;
  activity_label: string | null;
  overlap_minutes: number;
  match_score: number;
  effective_minutes: number;
  matched_context_tags: string[];
};

export type TaskAnalysisDetail = TaskAnalysis & {
  contributions: BehaviorContribution[];
};

export type DailyAnalytics = {
  date: string;
  summary: {
    day_minutes: number;
    tracked_minutes: number;
    unaccounted_minutes: number;
    behavior_count: number;
  };
  categories: { category: string; duration_minutes: number }[];
  activities: { category: string; activity_label: string | null; duration_minutes: number }[];
  tasks: {
    count: number;
    planned_minutes: number;
    effective_minutes: number;
    completion_rate: number;
  };
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

export const getTasks = (date: string, tzOffsetMinutes: number) =>
  request<Task[]>(`/api/tasks?date=${date}&tz_offset_minutes=${tzOffsetMinutes}`);

export const getTaskAnalysisForDay = (date: string, tzOffsetMinutes: number) =>
  request<TaskAnalysis[]>(
    `/api/tasks/analysis?date=${date}&tz_offset_minutes=${tzOffsetMinutes}`,
  );

export const getTaskAnalysis = (taskId: string) =>
  request<TaskAnalysisDetail>(`/api/tasks/${taskId}/analysis`);

export const createTask = (body: Record<string, unknown>) =>
  request<Task>("/api/tasks", { method: "POST", body: JSON.stringify(body) });

export const updateTask = (taskId: string, body: Record<string, unknown>) =>
  request<Task>(`/api/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(body) });

export const deleteTask = (taskId: string) =>
  request<void>(`/api/tasks/${taskId}`, { method: "DELETE" });

export const getDailyAnalytics = (date: string, tzOffsetMinutes: number) =>
  request<DailyAnalytics>(
    `/api/analytics/daily?date=${date}&tz_offset_minutes=${tzOffsetMinutes}`,
  );

export type PatternWindow = {
  start_date: string;
  end_date: string;
  behavior_count: number;
};

export type CategoryTransition = {
  type: "category_transition";
  from_category: string;
  to_category: string;
  count: number;
  probability: number;
  transitions_from_source: number;
};

export type ActivityTransition = {
  type: "activity_transition";
  from_category: string;
  from_activity: string;
  to_category: string;
  to_activity: string;
  count: number;
  probability: number;
  transitions_from_source: number;
};

export type TransitionPatterns = {
  window: PatternWindow;
  minimum_transition_count: number;
  category_transitions: CategoryTransition[];
  activity_transitions: ActivityTransition[];
};

export type ContextStat = {
  type: "context_stat";
  category: string;
  activity_label: string | null;
  dimension: string;
  context: string;
  session_count: number;
  total_duration_minutes: number;
  average_duration_minutes: number;
};

export type ContextAssociation = {
  type: "context_association";
  category: string;
  activity_label: string | null;
  dimension: string;
  context_a: string;
  context_b: string;
  average_duration_a: number;
  average_duration_b: number;
  sample_a: number;
  sample_b: number;
  difference_minutes: number;
  ratio: number;
};

export type ContextPatterns = {
  window: PatternWindow;
  minimum_context_sessions: number;
  context_stats: ContextStat[];
  associations: ContextAssociation[];
};

const patternQuery = (startDate: string, endDate: string, tzOffsetMinutes: number) =>
  `start_date=${startDate}&end_date=${endDate}&tz_offset_minutes=${tzOffsetMinutes}`;

export const getTransitionPatterns = (
  startDate: string,
  endDate: string,
  tzOffsetMinutes: number,
) =>
  request<TransitionPatterns>(
    `/api/patterns/transitions?${patternQuery(startDate, endDate, tzOffsetMinutes)}`,
  );

export const getContextPatterns = (
  startDate: string,
  endDate: string,
  tzOffsetMinutes: number,
) =>
  request<ContextPatterns>(
    `/api/patterns/context?${patternQuery(startDate, endDate, tzOffsetMinutes)}`,
  );

export type ChatRole = "user" | "assistant";

export type ChatMessage = {
  role: ChatRole;
  content: string;
};

export type ChatResponse = {
  reply: string;
  date: string;
};

export const sendChat = (body: {
  message: string;
  date: string;
  tz_offset_minutes: number;
  history: ChatMessage[];
}) =>
  request<ChatResponse>("/api/insights/chat", {
    method: "POST",
    body: JSON.stringify(body),
  });