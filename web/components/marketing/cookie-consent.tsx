"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Toggle } from "@/components/ui/toggle";
import {
  CONSENT_CHANGED_EVENT,
  OPEN_PREFERENCES_EVENT,
  makeConsent,
  readConsent,
  saveConsent,
  type CookieConsent,
} from "@/lib/cookie-consent";

/**
 * The cookie banner and the preferences dialog (plan 8.20). Nothing optional is on until the visitor
 * chooses, and "Reject" is exactly as easy as "Accept". The banner is not a modal: the page behind
 * it stays usable. It shows only on the public website; the signed-in app never loads it.
 */
export function CookieConsentManager() {
  const [ready, setReady] = useState(false);
  const [consent, setConsent] = useState<CookieConsent | null>(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [marketing, setMarketing] = useState(false);

  const openPreferences = useCallback((current: CookieConsent | null) => {
    setMarketing(current?.marketing ?? false);
    setDialogOpen(true);
  }, []);

  useEffect(() => {
    // The choice lives in localStorage, which the server cannot see, so it is read once the page is up.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setConsent(readConsent());
    setReady(true);
  }, []);

  useEffect(() => {
    const open = () => openPreferences(readConsent());
    window.addEventListener(OPEN_PREFERENCES_EVENT, open);
    return () => window.removeEventListener(OPEN_PREFERENCES_EVENT, open);
  }, [openPreferences]);

  const decide = (allowMarketing: boolean) => {
    const choice = makeConsent(allowMarketing, new Date());
    saveConsent(choice);
    setConsent(choice);
    setDialogOpen(false);
    window.dispatchEvent(new CustomEvent(CONSENT_CHANGED_EVENT, { detail: choice }));
  };

  const showBanner = ready && consent === null && !dialogOpen;

  return (
    <>
      {/* Lets a browser test (and nothing else) tell when the stored choice has been read. */}
      <div hidden data-consent-state={!ready ? "loading" : consent ? "decided" : "undecided"} />
      {showBanner ? (
        <section
          aria-label="Cookies"
          className="material-sheet shadow-e3 rounded-sheet fixed inset-x-3 bottom-3 z-30 mx-auto max-w-3xl p-4 md:p-5"
        >
          <p className="text-callout text-label">
            We use cookies that keep the site working. With your say-so we would also use marketing
            cookies, on this website only, to see which of our adverts help. Nothing optional is
            switched on until you choose.
          </p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button variant="tinted" size="sm" className="text-label" onClick={() => decide(false)}>
              Reject all
            </Button>
            <Button variant="tinted" size="sm" className="text-label" onClick={() => decide(true)}>
              Accept all
            </Button>
            <Button variant="plain" size="sm" onClick={() => openPreferences(consent)}>
              Choose
            </Button>
          </div>
        </section>
      ) : null}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent
          title="Cookie settings"
          description="Choose which cookies we may use. You can change this at any time from the link in the footer."
          footer={
            <>
              <Button variant="gray" onClick={() => decide(false)}>
                Reject all
              </Button>
              <Button onClick={() => decide(marketing)}>Save choices</Button>
            </>
          }
        >
          <div className="flex flex-col gap-5">
            <div>
              <p className="text-headline text-label">Necessary</p>
              <p className="text-subheadline text-label-secondary">
                Always on. They keep you signed in, remember your choices and protect forms from
                misuse. They never track you across other sites.
              </p>
            </div>
            <Toggle
              label="Marketing"
              description="Lets us measure which of our adverts brought you here. Only on this website, never inside the app."
              checked={marketing}
              onCheckedChange={setMarketing}
            />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

/** The footer's "Cookie settings" link: opens the preferences dialog. */
export function CookieSettingsButton({ className }: { className?: string }) {
  return (
    <button
      type="button"
      className={className}
      onClick={() => window.dispatchEvent(new Event(OPEN_PREFERENCES_EVENT))}
    >
      Cookie settings
    </button>
  );
}
