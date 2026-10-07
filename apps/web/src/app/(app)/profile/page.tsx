import { SignOutButton } from "@clerk/nextjs";
import { currentUser } from "@clerk/nextjs/server";

import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";

export default async function ProfilePage() {
  const user = await currentUser();

  const name =
    [user?.firstName, user?.lastName].filter(Boolean).join(" ") ||
    user?.username ||
    "—";
  const email = user?.primaryEmailAddress?.emailAddress ?? "—";

  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header>
        <h1 className="text-lg font-semibold tracking-tight">Profile</h1>
        <p className="text-sm text-muted-foreground">Your account details.</p>
      </header>

      <div className="flex flex-col gap-1.5">
        <span className="text-xs tracking-wide text-muted-foreground uppercase">
          Name
        </span>
        <span className="text-sm font-medium">{name}</span>
      </div>

      <div className="flex flex-col gap-1.5">
        <span className="text-xs tracking-wide text-muted-foreground uppercase">
          Email
        </span>
        <span className="text-sm font-medium">{email}</span>
      </div>

      <Separator />

      <div>
        <SignOutButton redirectUrl="/sign-in">
          <Button variant="outline">Sign Out</Button>
        </SignOutButton>
      </div>
    </div>
  );
}
