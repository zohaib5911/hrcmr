import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { SettingsAdmin } from "@/components/platform/settings-admin";
import { platformApi, dataOrSessionRedirect, sessionStartPath } from "@/lib/platform/guard";
export const metadata: Metadata = { title: "Settings", robots: { index: false, follow: false } };
export default async function Page() {
  const api = await platformApi();
  if (!api) redirect(sessionStartPath("/settings"));
  const [terms, flags, announcements, context] = await Promise.all([
    api.GET("/platform/terms-versions").catch(() => null),
    api.GET("/platform/feature-flags").catch(() => null),
    api.GET("/platform/announcements").catch(() => null),
    api.GET("/platform/context").catch(() => null),
  ]);
  return (
    <main className="min-h-dvh bg-grouped p-5 sm:p-8">
      <div className="mx-auto max-w-4xl">
        <SettingsAdmin
          terms={terms ? dataOrSessionRedirect(terms, "/settings") : null}
          flags={flags ? dataOrSessionRedirect(flags, "/settings") : null}
          announcements={announcements ? dataOrSessionRedirect(announcements, "/settings") : null}
          owner={context ? (dataOrSessionRedirect(context, "/settings")?.owner ?? false) : false}
        />
      </div>
    </main>
  );
}
