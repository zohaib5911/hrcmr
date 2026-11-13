"use client";

import { MapPin } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { PageHeader } from "@/components/app/page-header";
import { useCan } from "@/components/app/session-context";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { GroupedList, GroupedRow } from "@/components/ui/grouped-list";
import { Icon } from "@/components/ui/icon";
import { StatusChip } from "@/components/ui/status-chip";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import { Toggle } from "@/components/ui/toggle";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";

import { FormSheet } from "./form-sheet";

type Location = components["schemas"]["LocationOut"];

interface Form {
  name: string;
  postcode: string;
  address_line1: string;
  address_line2: string;
  address_line3: string;
  city: string;
  county: string;
  country: string;
  is_default: boolean;
}

const EMPTY: Form = {
  name: "",
  postcode: "",
  address_line1: "",
  address_line2: "",
  address_line3: "",
  city: "",
  county: "",
  country: "United Kingdom",
  is_default: false,
};

const formOf = (location: Location): Form => ({
  name: location.name,
  postcode: location.postcode,
  address_line1: location.address_line1,
  address_line2: location.address_line2 ?? "",
  address_line3: location.address_line3 ?? "",
  city: location.city,
  county: location.county ?? "",
  country: location.country,
  is_default: location.is_default,
});

const REQUIRED: Partial<Record<keyof Form, string>> = {
  name: "Give the location a name.",
  postcode: "Enter a postcode.",
  address_line1: "Enter the first line of the address.",
  city: "Enter the town or city.",
  country: "Enter the country.",
};

/** `/company/locations` (plan 8.15): the places the company works from. */
export function LocationsPage({ locations }: { locations: Location[] }) {
  const can = useCan();
  const mayEdit = can("company.location.write");
  const [editing, setEditing] = useState<Location | "new" | null>(null);

  return (
    <>
      <PageHeader
        title="Locations"
        description="The places your company works from. One is the main address."
        actions={
          mayEdit && locations.length > 0 ? (
            <Button onClick={() => setEditing("new")}>Add location</Button>
          ) : null
        }
      />
      {locations.length === 0 ? (
        <div className="bg-elevated rounded-card shadow-e1">
          <EmptyState
            icon={MapPin}
            title="No locations yet"
            description="Add your main address first. Employees, rotas and documents can then say where they are."
            {...(mayEdit
              ? { action: <Button onClick={() => setEditing("new")}>Add location</Button> }
              : {})}
          />
        </div>
      ) : (
        <GroupedList heading="Your locations">
          {locations.map((location) => (
            <GroupedRow
              key={location.id}
              title={location.name}
              icon={<Icon icon={MapPin} />}
              detail={
                <span className="flex items-center gap-2">
                  {location.is_default ? <StatusChip tone="info">Main</StatusChip> : null}
                  {location.postcode}, {location.city}
                </span>
              }
              {...(mayEdit ? { onClick: () => setEditing(location) } : {})}
            />
          ))}
        </GroupedList>
      )}
      {editing ? (
        <LocationSheet
          key={editing === "new" ? "new" : editing.id}
          location={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      ) : null}
    </>
  );
}

function LocationSheet({ location, onClose }: { location: Location | null; onClose: () => void }) {
  const router = useRouter();
  const toast = useToast();
  const [form, setForm] = useState<Form>(location ? formOf(location) : EMPTY);
  const [errors, setErrors] = useState<Partial<Record<keyof Form, string>>>({});
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const [lookup, setLookup] = useState<{ busy: boolean; message?: string; failed?: boolean }>({
    busy: false,
  });
  const set = <K extends keyof Form>(key: K, value: Form[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  async function look() {
    setLookup({ busy: true });
    const outcome = await attempt((client) =>
      client.GET("/locations/lookup/{postcode}", { params: { path: { postcode: form.postcode } } }),
    );
    if (!outcome.ok) {
      setLookup({ busy: false, failed: true, message: outcome.problem.message });
      return;
    }
    const found = outcome.data;
    setForm((current) => ({
      ...current,
      postcode: found.postcode,
      city: found.city ?? current.city,
      county: found.county ?? current.county,
      country: found.country ?? current.country,
    }));
    setLookup({ busy: false, message: "Town, county and country filled in. Add the street." });
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    const found: typeof errors = {};
    for (const [key, message] of Object.entries(REQUIRED) as [keyof Form, string][]) {
      if (!String(form[key]).trim()) found[key] = message;
    }
    setErrors(found);
    setProblem(null);
    if (Object.keys(found).length > 0) return;
    const body = {
      ...form,
      address_line2: form.address_line2.trim() || null,
      address_line3: form.address_line3.trim() || null,
      county: form.county.trim() || null,
    };
    setBusy(true);
    const outcome = await attempt((client) =>
      location
        ? client.PATCH("/locations/{location_id}", {
            params: { path: { location_id: location.id } },
            body,
          })
        : client.POST("/locations", { body }),
    );
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: location ? "Location saved" : "Location added", tone: "success" });
      router.refresh();
      onClose();
      return;
    }
    const { field, message } = outcome.problem;
    if (field && field in form) setErrors({ [field]: message });
    else setProblem(outcome.problem);
  }

  async function archive() {
    if (!location) return;
    const outcome = await attempt((client) =>
      client.DELETE("/locations/{location_id}", {
        params: { path: { location_id: location.id } },
      }),
    );
    if (outcome.ok) {
      toast.show({ title: "Location archived", tone: "success" });
      router.refresh();
      onClose();
    } else setProblem(outcome.problem);
  }

  return (
    <FormSheet
      open
      onOpenChange={(open) => !open && onClose()}
      title={location ? "Edit location" : "Add location"}
      description="Where people work, or where documents are kept."
      onSubmit={save}
      busy={busy}
      problem={problem}
      {...(location
        ? {
            archive: {
              label: "Archive",
              question: `Archive ${location.name}?`,
              detail: "It stops appearing in lists. Anything that used it keeps its record.",
              onConfirm: archive,
            },
          }
        : {})}
    >
      <TextField
        label="Name"
        name="name"
        autoFocus
        value={form.name}
        onChange={(event) => set("name", event.target.value)}
        error={errors.name}
        hint="For example Head office or Leeds depot."
      />
      <TextField
        label="Postcode"
        name="postcode"
        autoComplete="postal-code"
        autoCapitalize="characters"
        spellCheck={false}
        value={form.postcode}
        onChange={(event) => set("postcode", event.target.value)}
        error={errors.postcode}
        endAdornment={
          <Button
            variant="gray"
            size="sm"
            loading={lookup.busy}
            aria-disabled={!form.postcode.trim() || undefined}
            onClick={() => form.postcode.trim() && void look()}
          >
            Look up
          </Button>
        }
      />
      {lookup.message ? (
        <Alert tone={lookup.failed ? "warning" : "success"} title={lookup.message} />
      ) : null}
      <TextField
        label="Address line 1"
        name="address_line1"
        autoComplete="address-line1"
        value={form.address_line1}
        onChange={(event) => set("address_line1", event.target.value)}
        error={errors.address_line1}
      />
      <TextField
        label="Address line 2"
        name="address_line2"
        autoComplete="address-line2"
        value={form.address_line2}
        onChange={(event) => set("address_line2", event.target.value)}
        error={errors.address_line2}
      />
      <TextField
        label="Address line 3"
        name="address_line3"
        autoComplete="address-line3"
        value={form.address_line3}
        onChange={(event) => set("address_line3", event.target.value)}
        error={errors.address_line3}
      />
      <TextField
        label="Town or city"
        name="city"
        autoComplete="address-level2"
        value={form.city}
        onChange={(event) => set("city", event.target.value)}
        error={errors.city}
      />
      <TextField
        label="County"
        name="county"
        autoComplete="address-level1"
        value={form.county}
        onChange={(event) => set("county", event.target.value)}
        error={errors.county}
      />
      <TextField
        label="Country"
        name="country"
        autoComplete="country-name"
        value={form.country}
        onChange={(event) => set("country", event.target.value)}
        error={errors.country}
      />
      <Toggle
        label="This is the main location"
        description={
          location?.is_default
            ? "To change the main location, make another one the main location."
            : "It becomes the default, and the current main location stops being it."
        }
        checked={form.is_default}
        disabled={location?.is_default === true}
        onCheckedChange={(checked) => set("is_default", checked)}
      />
    </FormSheet>
  );
}
