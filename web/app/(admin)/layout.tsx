import type { ReactNode } from "react";

import { PlatformBar } from "@/components/platform/platform-bar";

/** Every platform admin page sits under this frame (T17.1): the red bar is always there. */
export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <PlatformBar />
      {children}
    </>
  );
}
