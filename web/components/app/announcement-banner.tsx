"use client";

import { useEffect, useState } from "react";

import { attempt } from "@/lib/auth/request";

const TIME = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "Europe/London",
});

type Live = { id: string; title: string; body: string; ends_at: string };

/**
 * Announcement banners (T17.5): the live notices for this company's region, from the platform's
 * scheduled banners. Nothing is shown when there are none, and a failed fetch shows nothing, so a
 * notice can never block the page.
 */
export function AnnouncementBanner() {
  const [items, setItems] = useState<Live[]>([]);

  useEffect(() => {
    let active = true;
    void attempt((client) => client.GET("/company/announcements")).then((outcome) => {
      if (active && outcome.ok) setItems(outcome.data.items);
    });
    return () => {
      active = false;
    };
  }, []);

  if (items.length === 0) return null;

  return (
    <section
      aria-label="Announcements"
      data-testid="announcement-banner"
      className="mb-6 flex flex-col gap-3"
    >
      {items.map((item) => (
        <div
          key={item.id}
          className="rounded-card border border-separator bg-elevated px-4 py-3 text-callout"
        >
          <p className="font-semibold text-label">{item.title}</p>
          <p className="mt-1 text-label-secondary">{item.body}</p>
          <p className="mt-1 text-footnote text-label-secondary">
            Shown until {TIME.format(new Date(item.ends_at))}
          </p>
        </div>
      ))}
    </section>
  );
}
