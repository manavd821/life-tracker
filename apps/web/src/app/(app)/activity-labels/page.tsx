import { AddActivityLabelForm, DeleteActivityLabelButton } from "@/components/activity-label-forms";
import { getActivityLabels } from "@/lib/backend";
import { CATEGORIES } from "@/lib/domain";

export default async function ActivityLabelsPage() {
  const labels = await getActivityLabels();

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header>
        <h1 className="text-lg font-semibold tracking-tight">Activity Labels</h1>
        <p className="text-sm text-muted-foreground">
          Labels are unique per category and scoped to your account.
        </p>
      </header>

      <AddActivityLabelForm />

      <section className="flex flex-col gap-4">
        {CATEGORIES.map((category) => {
          const items = labels.filter((label) => label.primary_category === category);
          if (items.length === 0) return null;

          return (
            <div key={category} className="flex flex-col gap-1.5">
              <h2 className="text-sm font-medium">{category}</h2>
              <ul className="flex flex-col divide-y divide-border rounded-lg border border-border">
                {items.map((label) => (
                  <li
                    key={label.activity_label_id}
                    className="flex items-center justify-between px-4 py-2 text-sm"
                  >
                    {label.activity_label}
                    <DeleteActivityLabelButton id={label.activity_label_id} />
                  </li>
                ))}
              </ul>
            </div>
          );
        })}

        {labels.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
            No activity labels yet.
          </p>
        ) : null}
      </section>
    </div>
  );
}