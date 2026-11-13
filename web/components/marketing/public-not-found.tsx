import { FileQuestion } from "lucide-react";
import Link from "next/link";

import { PublicContentFrame } from "@/components/marketing/public-content";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";

export function PublicNotFound() {
  return (
    <section aria-label="Page not found" className="bg-canvas text-label min-h-[60vh]">
      <PublicContentFrame>
        <h1 className="text-large-title text-center">Page not found</h1>
        <EmptyState
          icon={FileQuestion}
          title="We could not find that page."
          description="Use the home page to find what you need."
          action={
            <Button asChild>
              <Link href="/">Go to the home page</Link>
            </Button>
          }
        />
      </PublicContentFrame>
    </section>
  );
}
