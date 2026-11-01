import Link from "next/link";

import { Avatar } from "@/components/ui/avatar";
import { SkeletonPerson } from "@/components/ui/skeleton";

import type { ShellUser } from "./shell-types";

/** The signed-in person, at the bottom of the sidebar. A link to their profile. */
export function UserCard({ user }: { user: ShellUser | null }) {
  if (!user) return <SkeletonPerson className="px-1" />;
  return (
    <Link
      href="/profile"
      className="rounded-control hover:bg-fill-secondary flex items-center gap-3 p-2 transition-colors motion-micro group-data-[collapsed=true]/shell:justify-center"
    >
      <Avatar name={user.name} size="sm" decorative />
      <span className="min-w-0 flex-1 group-data-[collapsed=true]/shell:sr-only">
        <span className="text-callout text-label block truncate font-medium">{user.name}</span>
        <span className="text-footnote text-label-secondary block truncate">{user.role}</span>
      </span>
    </Link>
  );
}
