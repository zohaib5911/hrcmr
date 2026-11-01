"use client";

import { useSyncExternalStore } from "react";

import { isApplePlatform } from "@/lib/platform";

const subscribeNever = () => () => {};

/**
 * Whether this is an Apple device, so shortcuts can say Cmd or Ctrl. The server cannot know, so it
 * answers "yes" and the browser corrects it straight after loading.
 */
export function useApple(): boolean {
  return useSyncExternalStore(
    subscribeNever,
    () => isApplePlatform(navigator.platform),
    () => true,
  );
}
