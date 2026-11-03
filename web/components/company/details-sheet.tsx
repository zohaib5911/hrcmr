"use client";

import { Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState, type FormEvent } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Combobox } from "@/components/ui/combobox";
import { FileDrop, type UploadItem } from "@/components/ui/file-drop";
import { Icon } from "@/components/ui/icon";
import { Select } from "@/components/ui/select";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { useToast } from "@/components/ui/toast";
import { Toggle } from "@/components/ui/toggle";
import { YesNo } from "@/components/ui/yes-no";
import type { components } from "@/lib/api/client";
import { attempt, type Problem } from "@/lib/auth/request";
import {
  changesBetween,
  formFrom,
  type CompanyDetails,
  type DetailsForm,
} from "@/lib/company/details";

import { LogoPicture } from "./logo-picture";

type Features = components["schemas"]["Features"];
type Options = components["schemas"]["CompanyOptions"];

interface DetailsSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  company: CompanyDetails;
  features: Features;
  options: Options;
}

/** The company's details, edited in a sheet (plan 8.15). Nothing is saved until Save. */
export function DetailsSheet({
  open,
  onOpenChange,
  company,
  features,
  options,
}: DetailsSheetProps) {
  const initial = useMemo(() => formFrom(company), [company]);
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      {open ? (
        <DetailsForm
          key={JSON.stringify(initial)}
          initial={initial}
          company={company}
          features={features}
          options={options}
          close={() => onOpenChange(false)}
        />
      ) : null}
    </Sheet>
  );
}

function DetailsForm({
  initial,
  company,
  features,
  options,
  close,
}: {
  initial: DetailsForm;
  company: CompanyDetails;
  features: Features;
  options: Options;
  close: () => void;
}) {
  const router = useRouter();
  const toast = useToast();
  const [form, setForm] = useState(initial);
  const [errors, setErrors] = useState<Partial<Record<keyof DetailsForm, string>>>({});
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const [lookup, setLookup] = useState<{ busy: boolean; message?: string; failed?: boolean }>({
    busy: false,
  });
  const [logo, setLogo] = useState<UploadItem[]>([]);
  const [logoChanged, setLogoChanged] = useState(0);

  const set = <K extends keyof DetailsForm>(key: K, value: DetailsForm[K]) =>
    setForm((current) => ({ ...current, [key]: value }));

  async function look() {
    setLookup({ busy: true });
    const outcome = await attempt((client) =>
      client.GET("/company/companies-house/{number}", {
        params: { path: { number: form.registered_number.trim() } },
      }),
    );
    if (!outcome.ok) {
      setLookup({ busy: false, failed: true, message: outcome.problem.message });
      return;
    }
    const found = outcome.data;
    setForm((current) => ({
      ...current,
      name: found.name || current.name,
      registered_number: found.number,
      type_of_organisation: found.legal_structure ?? current.type_of_organisation,
    }));
    setLookup({
      busy: false,
      message: `Found ${found.name}. Check the name and legal structure, then save.`,
    });
  }

  async function uploadLogo(files: File[]) {
    const file = files[0];
    if (!file) return;
    const id = `${file.name}-${file.size}`;
    setLogo([{ id, name: file.name, size: file.size, status: "scanning" }]);
    const body = new FormData();
    body.append("file", file);
    const outcome = await attempt((client) =>
      client.POST("/company/logo", { body: { file: "" }, bodySerializer: () => body }),
    );
    if (outcome.ok) {
      setLogo([{ id, name: file.name, size: file.size, status: "safe" }]);
      setLogoChanged((count) => count + 1);
      router.refresh();
    } else {
      setLogo([
        {
          id,
          name: file.name,
          size: file.size,
          status: "rejected",
          message: outcome.problem.message,
        },
      ]);
    }
  }

  async function removeLogo() {
    const outcome = await attempt((client) => client.DELETE("/company/logo"));
    if (outcome.ok) {
      setLogo([]);
      setLogoChanged((count) => count + 1);
      router.refresh();
    } else setProblem(outcome.problem);
  }

  async function save(event: FormEvent) {
    event.preventDefault();
    const found: typeof errors = {
      ...(form.name.trim() ? {} : { name: "Enter the company name." }),
      ...(form.timezone ? {} : { timezone: "Choose a time zone." }),
      ...(form.changed_name_last_5_years && !form.previous_company_name.trim()
        ? { previous_company_name: "Enter the previous name." }
        : {}),
      ...(form.penalty_illegal_working_last_3_years && !form.penalty_illegal_working_status.trim()
        ? { penalty_illegal_working_status: "Say what the status of the penalty is." }
        : {}),
    };
    setErrors(found);
    setProblem(null);
    if (Object.keys(found).length > 0) return;
    const changes = changesBetween(initial, form);
    if (Object.keys(changes).length === 0) {
      close();
      return;
    }
    setBusy(true);
    const outcome = await attempt((client) => client.PATCH("/company", { body: changes }));
    setBusy(false);
    if (outcome.ok) {
      toast.show({ title: "Company details saved", tone: "success" });
      router.refresh();
      close();
      return;
    }
    const { field, message } = outcome.problem;
    if (field && field in form) setErrors({ [field]: message });
    else setProblem(outcome.problem);
  }

  const zones = useMemo(
    () => options.timezones.map((zone) => ({ value: zone, label: zone })),
    [options],
  );

  return (
    <SheetContent
      title="Company details"
      description="What your company is called and how to reach it."
      footer={
        <>
          <Button variant="gray" onClick={close}>
            Cancel
          </Button>
          <Button type="submit" form="company-details" loading={busy}>
            Save
          </Button>
        </>
      }
    >
      <form id="company-details" onSubmit={save} noValidate className="flex flex-col gap-5 pb-2">
        {problem ? <Alert tone="danger" title={problem.message} /> : null}

        <fieldset className="flex flex-col gap-3">
          <legend className="text-headline text-label mb-1">Logo</legend>
          <div className="flex items-center gap-4">
            <LogoPicture
              name={company.name}
              hasLogo={company.has_logo}
              size="lg"
              version={logoChanged}
            />
            {company.has_logo ? (
              <Button variant="gray" size="sm" onClick={() => void removeLogo()}>
                <Icon icon={Trash2} size={16} />
                Remove
              </Button>
            ) : null}
          </div>
          <FileDrop
            label="Upload a logo"
            description="A PNG or JPG, up to 2 MB."
            accept={["image/png", "image/jpeg"]}
            maxBytes={2 * 1024 * 1024}
            items={logo}
            onFiles={(files) => void uploadLogo(files)}
            onRemove={() => setLogo([])}
          />
        </fieldset>

        <div className="flex flex-col gap-3">
          <TextField
            label="Company name"
            name="name"
            autoComplete="organization"
            required
            value={form.name}
            onChange={(event) => set("name", event.target.value)}
            error={errors.name}
          />
          <TextField
            label="Trading name"
            name="trading_name"
            value={form.trading_name}
            onChange={(event) => set("trading_name", event.target.value)}
            error={errors.trading_name}
          />
          <TextField
            label="Companies House number"
            name="registered_number"
            autoCapitalize="characters"
            spellCheck={false}
            value={form.registered_number}
            onChange={(event) => set("registered_number", event.target.value)}
            error={errors.registered_number}
            hint="Eight letters or digits, such as 01234567."
            endAdornment={
              features.companies_house_lookup ? (
                <Button
                  variant="gray"
                  size="sm"
                  loading={lookup.busy}
                  onClick={() => void look()}
                  aria-disabled={!form.registered_number.trim() || undefined}
                >
                  Look up
                </Button>
              ) : null
            }
          />
          {lookup.message ? (
            <Alert tone={lookup.failed ? "warning" : "success"} title={lookup.message} />
          ) : null}
        </div>

        <div className="flex flex-col gap-3">
          <Select
            label="Legal structure"
            name="type_of_organisation"
            placeholder="Choose one"
            value={form.type_of_organisation}
            onChange={(event) => set("type_of_organisation", event.target.value)}
            error={errors.type_of_organisation}
          >
            {options.legal_structures.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
          <Select
            label="Trading period"
            name="trading_period"
            placeholder="Choose one"
            value={form.trading_period}
            onChange={(event) => set("trading_period", event.target.value)}
            error={errors.trading_period}
          >
            {options.trading_periods.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
          <Select
            label="Sector"
            name="sector"
            placeholder="Choose one"
            value={form.sector}
            onChange={(event) => set("sector", event.target.value)}
            error={errors.sector}
          >
            {options.sectors.map((option) => (
              <option key={option.value} value={option.value}>
                {option.value}. {option.label}
              </option>
            ))}
          </Select>
        </div>

        <fieldset className="flex flex-col gap-3">
          <legend className="text-headline text-label mb-1">Sponsor history</legend>
          <YesNo
            label="Has the company changed its name in the last 5 years?"
            value={form.changed_name_last_5_years}
            onChange={(value) => set("changed_name_last_5_years", value)}
          />
          {form.changed_name_last_5_years ? (
            <TextField
              label="Previous company name"
              name="previous_company_name"
              value={form.previous_company_name}
              onChange={(event) => set("previous_company_name", event.target.value)}
              error={errors.previous_company_name}
            />
          ) : null}
          <YesNo
            label="Has the company had a penalty for illegal working in the last 3 years?"
            value={form.penalty_illegal_working_last_3_years}
            onChange={(value) => set("penalty_illegal_working_last_3_years", value)}
          />
          {form.penalty_illegal_working_last_3_years ? (
            <TextArea
              label="Status of the penalty"
              name="penalty_illegal_working_status"
              rows={3}
              value={form.penalty_illegal_working_status}
              onChange={(event) => set("penalty_illegal_working_status", event.target.value)}
              error={errors.penalty_illegal_working_status}
            />
          ) : null}
        </fieldset>

        <fieldset className="flex flex-col gap-3">
          <legend className="text-headline text-label mb-1">Contact</legend>
          <TextField
            label="Contact email"
            type="email"
            name="contact_email"
            inputMode="email"
            autoCapitalize="none"
            spellCheck={false}
            value={form.contact_email}
            onChange={(event) => set("contact_email", event.target.value)}
            error={errors.contact_email}
          />
          <TextField
            label="Phone"
            type="tel"
            name="contact_phone"
            autoComplete="tel"
            value={form.contact_phone}
            onChange={(event) => set("contact_phone", event.target.value)}
            error={errors.contact_phone}
          />
          <TextField
            label="Website"
            type="url"
            name="website"
            inputMode="url"
            autoCapitalize="none"
            spellCheck={false}
            value={form.website}
            onChange={(event) => set("website", event.target.value)}
            error={errors.website}
            hint="Start with https://"
          />
        </fieldset>

        <fieldset className="flex flex-col gap-3">
          <legend className="text-headline text-label mb-1">Where and when</legend>
          <Combobox
            label="Time zone"
            options={zones}
            value={form.timezone ? { value: form.timezone, label: form.timezone } : null}
            onChange={(option) => set("timezone", option?.value ?? "")}
            error={errors.timezone}
          />
          <Select
            label="Bank holidays"
            name="bank_holiday_region"
            value={form.bank_holiday_region}
            onChange={(event) => set("bank_holiday_region", event.target.value)}
            error={errors.bank_holiday_region}
          >
            {options.bank_holiday_regions.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </Select>
        </fieldset>

        <Toggle
          label="Allow optional clock location"
          description="Employees may share their location when clocking in or out. Each action needs their consent."
          checked={form.clock_geolocation_enabled}
          onCheckedChange={(checked) => set("clock_geolocation_enabled", checked)}
        />

        {features.ai ? (
          <Toggle
            label="AI features"
            description="Letter drafting, reminder wording and other helpers. Off keeps your data away from AI entirely."
            checked={form.ai_features_enabled}
            onCheckedChange={(checked) => set("ai_features_enabled", checked)}
          />
        ) : null}
      </form>
    </SheetContent>
  );
}
