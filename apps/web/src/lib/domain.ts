export const CATEGORIES = [
  "Entertainment",
  "Study",
  "Health",
  "Work",
  "Travel",
  "Social",
  "Rest",
  "Admin",
] as const;

export const ENERGY_LEVELS = ["High", "Medium", "Low"] as const;
export const EMOTION_STATES = ["Calm", "Stressed", "Neutral", "Irritated"] as const;
export const FOCUS_STATES = ["Focused", "Neutral", "Distracted"] as const;
export const ENVIRONMENTS = [
  "Home",
  "College",
  "Library",
  "PG",
  "Travel",
  "Gym",
  "Office",
] as const;

export const PRECISIONS = ["HIGH", "LOW"] as const;

export function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest}m`;
  if (rest === 0) return `${hours}h`;
  return `${hours}h ${rest}m`;
}

export function formatClock(iso: string): string {
  return new Date(iso).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function localDateString(date: Date): string {
  const year = date.getFullYear();
  const month = `${date.getMonth() + 1}`.padStart(2, "0");
  const day = `${date.getDate()}`.padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function timezoneOffsetMinutes(date: Date): number {
  return -date.getTimezoneOffset();
}

export function toIsoWithOffset(date: Date, hours: number, minutes: number): string {
  const local = new Date(date);
  local.setHours(hours, minutes, 0, 0);
  return local.toISOString();
}

export function splitIso(iso: string): { hours: number; minutes: number } {
  const parsed = new Date(iso);
  return { hours: parsed.getHours(), minutes: parsed.getMinutes() };
}

export function formatRate(rate: number): string {
  const rounded = Math.round(rate * 10) / 10;
  return `${Number.isInteger(rounded) ? rounded : rounded.toFixed(1)}%`;
}

export function formatProbability(probability: number): string {
  const percent = Math.round(probability * 1000) / 10;
  return `${Number.isInteger(percent) ? percent : percent.toFixed(1)}%`;
}

export function formatMinutes(value: number): string {
  return Number.isInteger(value) ? `${value}` : value.toFixed(2).replace(/\.?0+$/, "");
}

export function dayKey(iso: string): string {
  return localDateString(new Date(iso));
}

export function parseLocalDate(value: string | undefined | null): Date | null {
  if (!value) return null;
  const [year, month, day] = value.split("-").map(Number);
  if ([year, month, day].some(Number.isNaN)) return null;
  return new Date(year, month - 1, day);
}

export function shiftDateString(value: string, days: number): string {
  const date = parseLocalDate(value) ?? new Date();
  date.setDate(date.getDate() + days);
  return localDateString(date);
}

export function weekdayLabel(value: string): string {
  return new Date(value).toLocaleDateString([], {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

export function dayLabel(iso: string): string {
  const key = dayKey(iso);
  const today = localDateString(new Date());
  if (key === today) return "Today";

  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  if (key === localDateString(tomorrow)) return "Tomorrow";

  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  if (key === localDateString(yesterday)) return "Yesterday";

  return new Date(iso).toLocaleDateString([], {
    weekday: "short",
    day: "numeric",
    month: "short",
  });
}