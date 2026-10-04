export type ActionState = {
  ok: boolean;
  message?: string;
  code?: string;
  conflicts?: string[];
  fieldErrors?: Record<string, string>;
};

export const idleState: ActionState = { ok: false };