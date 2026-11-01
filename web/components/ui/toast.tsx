"use client";

import { CircleAlert, CircleCheck, Info, TriangleAlert, X } from "lucide-react";
import { Toast as ToastPrimitive } from "radix-ui";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

import { Button, IconButton } from "./button";
import { Icon } from "./icon";

type ToastTone = "info" | "success" | "warning" | "danger";

export interface ToastInput {
  title: string;
  description?: string;
  tone?: ToastTone;
  /** For something reversible: "Undo". It keeps the toast on screen longer. */
  action?: { label: string; onClick: () => void };
  /** Milliseconds. Defaults to 5 s, or 8 s with an action. */
  duration?: number;
}

interface ToastItem extends ToastInput {
  id: number;
}

const ToastContext = createContext<{ show: (toast: ToastInput) => void } | null>(null);

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside <ToastProvider>.");
  return context;
}

const GLYPHS = {
  info: Info,
  success: CircleCheck,
  warning: TriangleAlert,
  danger: CircleAlert,
} as const;
const TONES = {
  info: "text-info",
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
} as const;

/** Put once near the root. Toasts appear top-centre, F8 jumps to them, and they pause while you read. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextId = useRef(0);

  const show = useCallback((toast: ToastInput) => {
    nextId.current += 1;
    const id = nextId.current;
    setToasts((current) => [...current, { ...toast, id }]);
  }, []);
  const value = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={value}>
      <ToastPrimitive.Provider swipeDirection="up" duration={5000} label="Notification">
        {children}
        {toasts.map((toast) => {
          const tone = toast.tone ?? "info";
          return (
            <ToastPrimitive.Root
              key={toast.id}
              // Errors interrupt; everything else waits for a pause.
              type={tone === "danger" ? "foreground" : "background"}
              duration={toast.duration ?? (toast.action ? 8000 : 5000)}
              onOpenChange={(open) => {
                if (!open) setToasts((current) => current.filter((t) => t.id !== toast.id));
              }}
              className={cn(
                "material-sheet rounded-popover shadow-e2 flex items-start gap-3 p-3 pr-2",
                "data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:slide-in-from-top-2",
                "data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:slide-out-to-top-2",
                "duration-[var(--duration-small)] motion-reduce:data-[state=open]:slide-in-from-top-0 motion-reduce:data-[state=closed]:slide-out-to-top-0",
              )}
            >
              <Icon icon={GLYPHS[tone]} className={cn("mt-0.5", TONES[tone])} />
              <div className="min-w-0 flex-1">
                <ToastPrimitive.Title className="text-headline text-label">
                  {toast.title}
                </ToastPrimitive.Title>
                {toast.description ? (
                  <ToastPrimitive.Description className="text-callout text-label-secondary">
                    {toast.description}
                  </ToastPrimitive.Description>
                ) : null}
              </div>
              {toast.action ? (
                <ToastPrimitive.Action altText={toast.action.label} asChild>
                  <Button size="sm" variant="tinted" onClick={toast.action.onClick}>
                    {toast.action.label}
                  </Button>
                </ToastPrimitive.Action>
              ) : null}
              <ToastPrimitive.Close asChild>
                <IconButton label="Dismiss notification" size="sm">
                  <Icon icon={X} size={16} />
                </IconButton>
              </ToastPrimitive.Close>
            </ToastPrimitive.Root>
          );
        })}
        <ToastPrimitive.Viewport className="fixed top-3 left-1/2 z-[60] flex w-[min(26rem,calc(100vw-1.5rem))] -translate-x-1/2 flex-col gap-2 pt-[env(safe-area-inset-top)] outline-none" />
      </ToastPrimitive.Provider>
    </ToastContext.Provider>
  );
}
