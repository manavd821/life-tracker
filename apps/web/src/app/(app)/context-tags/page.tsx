import { AddContextTagForm, DeleteContextTagButton } from "@/components/context-tag-forms";
import { getContextTags } from "@/lib/backend";
import { CATEGORIES } from "@/lib/domain";

export default async function ContextTagsPage() {
  const tags = await getContextTags();

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header>
        <h1 className="text-lg font-semibold tracking-tight">Context Tags</h1>
        <p className="text-sm text-muted-foreground">
          Tags are unique per category and can be attached to behaviors.
        </p>
      </header>

      <AddContextTagForm />

      <section className="flex flex-col gap-4">
        {CATEGORIES.map((category) => {
          const items = tags.filter((tag) => tag.primary_category === category);
          if (items.length === 0) return null;

          return (
            <div key={category} className="flex flex-col gap-1.5">
              <h2 className="text-sm font-medium">{category}</h2>
              <ul className="flex flex-col divide-y divide-border rounded-lg border border-border">
                {items.map((tag) => (
                  <li
                    key={tag.behavior_context_tag_id}
                    className="flex items-center justify-between px-4 py-2 text-sm"
                  >
                    {tag.context_tag}
                    <DeleteContextTagButton id={tag.behavior_context_tag_id} />
                  </li>
                ))}
              </ul>
            </div>
          );
        })}

        {tags.length === 0 ? (
          <p className="rounded-lg border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
            No context tags yet.
          </p>
        ) : null}
      </section>
    </div>
  );
}