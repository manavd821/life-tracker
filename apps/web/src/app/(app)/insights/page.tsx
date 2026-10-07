import { AiChat } from "@/components/ai-chat";
import { DateNavigator } from "@/components/date-navigator";
import {
  localDateString,
  parseLocalDate,
  timezoneOffsetMinutes,
  weekdayLabel,
} from "@/lib/domain";

export default async function InsightsPage({
  searchParams,
}: {
  searchParams: Promise<{ date?: string }>;
}) {
  const { date } = await searchParams;
  const selected = parseLocalDate(date) ?? new Date();
  const targetDate = localDateString(selected);
  const offset = timezoneOffsetMinutes(selected);

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Insights</h1>
          <p className="text-sm text-muted-foreground">{weekdayLabel(targetDate)}</p>
        </div>
        <DateNavigator
          date={targetDate}
          href={(day) => `/insights?date=${day}`}
          todayHref="/insights"
        />
      </header>

      <AiChat key={targetDate} date={targetDate} tzOffsetMinutes={offset} />
    </div>
  );
}
