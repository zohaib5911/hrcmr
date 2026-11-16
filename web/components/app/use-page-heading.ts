"use client";

import { useEffect, useState } from "react";

/** Follow the real page heading, including headings loaded after navigation. */
export function usePageHeading(pathname: string) {
  const [heading, setHeading] = useState({ path: "", title: "", visible: true });
  useEffect(() => {
    const main = document.querySelector("main");
    if (!main || typeof IntersectionObserver === "undefined") return;
    let current: Element | null = null;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry)
          setHeading({
            path: pathname,
            title: current?.textContent?.trim() ?? "",
            visible: entry.isIntersecting,
          });
      },
      { rootMargin: "-56px 0px 0px 0px" },
    );
    const update = () => {
      const next = main.querySelector("h1");
      if (next !== current) {
        observer.disconnect();
        current = next;
        if (current) observer.observe(current);
      }
      setHeading((previous) => ({
        path: pathname,
        title: current?.textContent?.trim() ?? "",
        visible: previous.path === pathname ? previous.visible : true,
      }));
    };
    const mutations = new MutationObserver(update);
    mutations.observe(main, { childList: true, subtree: true, characterData: true });
    update();
    return () => {
      mutations.disconnect();
      observer.disconnect();
    };
  }, [pathname]);
  return heading.path === pathname ? heading : { title: "", visible: true };
}
