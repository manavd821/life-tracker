export function Skeleton({ className }: { className?: string }) {
  return <div className={`rounded-md bg-muted ${className ?? ""}`} />;
}