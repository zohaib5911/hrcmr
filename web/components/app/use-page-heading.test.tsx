// @vitest-environment jsdom
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { usePageHeading } from "./use-page-heading";

afterEach(() => {
  vi.unstubAllGlobals();
  document.querySelector("main")?.remove();
});

it("tracks a loaded record heading and reveals the compact title only after it leaves view", async () => {
  let notify: IntersectionObserverCallback = () => {};
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(callback: IntersectionObserverCallback) {
        notify = callback;
      }
      observe = vi.fn();
      disconnect = vi.fn();
    },
  );
  const main = document.createElement("main");
  document.body.append(main);
  const { result } = renderHook(() => usePageHeading("/employees/person"));
  act(() => {
    main.innerHTML = "<h1>Cara Doyle</h1>";
  });
  await waitFor(() => expect(result.current.title).toBe("Cara Doyle"));
  expect(result.current.visible).toBe(true);
  act(() =>
    notify([{ isIntersecting: false } as IntersectionObserverEntry], {} as IntersectionObserver),
  );
  expect(result.current.visible).toBe(false);
  act(() =>
    notify([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver),
  );
  expect(result.current.visible).toBe(true);
});
