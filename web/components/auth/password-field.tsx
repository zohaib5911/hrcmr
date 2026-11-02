"use client";

import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";

import { IconButton } from "@/components/ui/button";
import { Icon } from "@/components/ui/icon";
import { TextField, type TextFieldProps } from "@/components/ui/text-field";
import { passwordStrength } from "@/lib/auth/password";
import { cn } from "@/lib/utils";

type PasswordFieldProps = Omit<TextFieldProps, "type" | "endAdornment" | "clearable"> & {
  /** Shows the strength meter under the field (for choosing a password, not for entering one). */
  meter?: boolean;
  value: string;
};

const BAR = ["bg-danger", "bg-danger", "bg-warning-fill", "bg-success-fill", "bg-success-fill"];

/** A password with a show/hide button, and optionally a meter that follows what is typed. */
export function PasswordField({ meter = false, value, hint, ...props }: PasswordFieldProps) {
  const [shown, setShown] = useState(false);
  const strength = passwordStrength(value);
  return (
    <div className="flex flex-col gap-2">
      <TextField
        {...props}
        value={value}
        type={shown ? "text" : "password"}
        clearable={false}
        autoCapitalize="none"
        spellCheck={false}
        {...(hint ? { hint } : {})}
        endAdornment={
          <IconButton
            label={shown ? "Hide password" : "Show password"}
            aria-pressed={shown}
            size="sm"
            variant="plain"
            onClick={() => setShown((current) => !current)}
          >
            <Icon icon={shown ? EyeOff : Eye} size={20} />
          </IconButton>
        }
      />
      {meter ? (
        <div className="flex flex-col gap-1.5 px-1">
          <div className="flex gap-1" aria-hidden="true">
            {[1, 2, 3, 4].map((step) => (
              <span
                key={step}
                className={cn(
                  "h-1 flex-1 rounded-full transition-colors motion-micro",
                  strength.level >= step ? BAR[strength.level] : "bg-fill-secondary",
                )}
              />
            ))}
          </div>
          <p className="text-footnote text-label-secondary" aria-live="polite">
            {strength.label ? (
              <strong className="text-label font-semibold">{strength.label}. </strong>
            ) : null}
            {strength.tip}
          </p>
        </div>
      ) : null}
    </div>
  );
}
