import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import type { ComponentProps, MouseEvent } from "react";

import { cn } from "@/lib/utils";

import { Spinner } from "./spinner";

export const buttonVariants = cva(
  [
    "relative inline-flex shrink-0 items-center justify-center gap-2 rounded-control font-semibold whitespace-nowrap select-none",
    "transition-[background-color,transform,opacity] motion-micro hit-target",
    // Pressed: 0.98 for 80 ms (lib/motion.ts PRESS); --press-scale is 1 with reduced motion.
    "active:scale-(--press-scale) active:duration-(--press-duration)",
    "disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none",
    // A button that is busy is not dimmed (it is working); one that is merely unavailable is.
    "[&[aria-disabled=true]:not([aria-busy=true])]:opacity-50",
  ],
  {
    variants: {
      variant: {
        filled: "bg-accent text-on-accent hover:bg-accent-pressed active:bg-accent-pressed",
        // Hover and press add a ring, not a stronger tint: the accent text has little contrast headroom on a heavier tint in dark mode.
        tinted:
          "bg-accent-tint text-accent-text hover:ring-1 hover:ring-accent/60 hover:ring-inset active:ring-2 active:ring-accent active:ring-inset",
        gray: "bg-fill-secondary text-label hover:bg-label/10 active:bg-label/15",
        plain: "text-accent-text hover:bg-accent-tint active:bg-accent/20",
        destructive: "bg-danger text-on-accent hover:opacity-90 active:opacity-80",
      },
      size: {
        sm: "h-8 px-3 text-callout",
        md: "h-10 px-4 text-body",
        lg: "h-12 px-6 text-headline",
      },
    },
    defaultVariants: { variant: "filled", size: "md" },
  },
);

type ButtonProps = ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    /** Shows a spinner, keeps the button's width, and ignores clicks. Not available with `asChild`. */
    loading?: boolean;
    /** Render the child element (for example a link) with the button's look. */
    asChild?: boolean;
  };

export function Button({
  className,
  variant,
  size,
  loading = false,
  asChild = false,
  children,
  onClick,
  type = "button",
  ...props
}: ButtonProps) {
  const classes = cn(buttonVariants({ variant, size }), className);

  if (asChild) {
    return (
      <Slot.Root className={classes} {...props}>
        {children}
      </Slot.Root>
    );
  }

  // `aria-disabled`, not `disabled`: a button that is busy keeps keyboard focus.
  const guard = (event: MouseEvent<HTMLButtonElement>) => {
    if (loading) event.preventDefault();
    else onClick?.(event);
  };

  return (
    <button
      type={type}
      className={classes}
      aria-busy={loading || undefined}
      aria-disabled={loading || undefined}
      onClick={guard}
      {...props}
    >
      <span className={cn("inline-flex items-center justify-center gap-2", loading && "opacity-0")}>
        {children}
      </span>
      {loading ? (
        <span className="absolute inset-0 grid place-items-center">
          <Spinner />
        </span>
      ) : null}
    </button>
  );
}

const ICON_SIZES = { sm: "size-8", md: "size-10", lg: "size-12" } as const;

type IconButtonProps = Omit<ButtonProps, "children" | "size" | "asChild"> & {
  /** What the button does. Icon-only buttons have no visible text, so this is required. */
  label: string;
  size?: keyof typeof ICON_SIZES;
};

export function IconButton({
  label,
  size = "md",
  variant = "plain",
  className,
  children,
  ...props
}: IconButtonProps & { children: ComponentProps<"span">["children"] }) {
  return (
    <Button
      aria-label={label}
      variant={variant}
      className={cn(ICON_SIZES[size], "px-0", className)}
      {...props}
    >
      {children}
    </Button>
  );
}
