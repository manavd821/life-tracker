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