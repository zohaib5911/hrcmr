import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface AuthCardProps {
  title: string;
  description?: ReactNode;
  children: ReactNode;
  className?: string;
}

/** The one panel every sign-in screen sits in: a heading, a sentence, then the form. */
export function AuthCard({ title, description, children, className }: AuthCardProps) {
  return (
    <section
      aria-labelledby="auth-title"
      className={cn(
        "bg-elevated rounded-card shadow-e2 flex w-full flex-col gap-6 p-6 sm:p-8",
        className,
      )}
    >
      <header className="flex flex-col gap-2">
        <h1 id="auth-title" className="text-title-2 text-label text-balance">
          {title}
        </h1>
        {description ? (
          <p className="text-body text-label-secondary text-pretty">{description}</p>
        ) : null}
      </header>
      {children}
    </section>
  );
}
