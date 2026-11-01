import { cva } from "class-variance-authority";
import { Avatar as RadixAvatar } from "radix-ui";

import { avatarTone, initials, type AvatarTone } from "@/lib/ui/avatar";
import { cn } from "@/lib/utils";

const TONES: Record<AvatarTone, string> = {
  accent: "bg-accent-tint text-accent-text",
  success: "bg-success-tint text-success",
  warning: "bg-warning-tint text-warning",
  danger: "bg-danger-tint text-danger",
  info: "bg-info-tint text-info",
  neutral: "bg-fill-secondary text-label",
};

export const avatarSize = cva(
  "rounded-pill inline-flex shrink-0 items-center justify-center overflow-hidden font-semibold select-none",
  {
    variants: {
      size: {
        xs: "size-6 text-caption",
        sm: "size-8 text-footnote",
        md: "size-10 text-callout",
        lg: "size-14 text-title-3",
      },
    },
    defaultVariants: { size: "md" },
  },
);

interface AvatarProps {
  name: string;
  src?: string;
  size?: "xs" | "sm" | "md" | "lg";
  className?: string;
  /** Set when the name is written out next to the avatar, so it is not announced twice. */
  decorative?: boolean;
}

/** A photo, or the person's initials on a soft colour that is the same every time. */
export function Avatar({ name, src, size, className, decorative = false }: AvatarProps) {
  return (
    <RadixAvatar.Root
      className={cn(avatarSize({ size }), TONES[avatarTone(name)], className)}
      {...(decorative
        ? { "aria-hidden": true }
        : { role: "img", "aria-label": name.trim() || "Unknown person" })}
    >
      {src ? <RadixAvatar.Image src={src} alt="" className="size-full object-cover" /> : null}
      <RadixAvatar.Fallback aria-hidden="true" delayMs={src ? 300 : 0}>
        {initials(name)}
      </RadixAvatar.Fallback>
    </RadixAvatar.Root>
  );
}

/** Overlapping avatars, with "+N" for the rest. */
export function AvatarStack({
  people,
  max = 4,
  size = "sm",
  className,
}: {
  people: readonly { name: string; src?: string }[];
  max?: number;
  size?: "xs" | "sm" | "md";
  className?: string;
}) {
  const shown = people.slice(0, max);
  const extra = people.length - shown.length;
  return (
    <div
      role="group"
      aria-label={`${people.length} ${people.length === 1 ? "person" : "people"}: ${people.map((p) => p.name).join(", ")}`}
      className={cn("flex items-center -space-x-2", className)}
    >
      {shown.map((person) => (
        <Avatar
          key={person.name}
          {...person}
          size={size}
          decorative
          className="ring-elevated ring-2"
        />
      ))}
      {extra > 0 ? (
        <span
          aria-hidden="true"
          className={cn(avatarSize({ size }), "bg-fill-secondary text-label ring-elevated ring-2")}
        >
          +{extra}
        </span>
      ) : null}
    </div>
  );
}
