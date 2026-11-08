"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Sheet, SheetContent } from "@/components/ui/sheet";

import { SponsorshipChecker } from "./checker";

type Props = {
  /** Gets the code once someone confirms it in the checker. */
  onFound: (code: string) => void;
  disabled?: boolean;
};

/**
 * "Find code": opens the sponsorship checker in a sheet. The code the person confirms fills the
 * field this sits beside, and the form is saved as usual (nothing is written here).
 */
export function FindCodeButton({ onFound, disabled = false }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button variant="gray" size="sm" onClick={() => setOpen(true)} disabled={disabled}>
        Find code
      </Button>
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetContent
          title="Find the SOC code"
          description="Check the job. The code you confirm fills in the field."
        >
          <SponsorshipChecker
            embedded
            onConfirmed={(code) => {
              onFound(code);
              setOpen(false);
            }}
          />
        </SheetContent>
      </Sheet>
    </>
  );
}
