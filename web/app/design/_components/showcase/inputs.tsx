"use client";

import { Mail } from "lucide-react";
import { useState } from "react";

import { Combobox, type ComboboxOption } from "@/components/ui/combobox";
import { DatePicker, DateRangePicker, type DateRange } from "@/components/ui/date-picker";
import { DateTimePicker } from "@/components/ui/date-time-picker";
import type { DayMarker } from "@/components/ui/calendar-month";
import { Icon } from "@/components/ui/icon";
import { NumberField } from "@/components/ui/number-field";
import { SearchField } from "@/components/ui/search-field";
import { Select } from "@/components/ui/select";
import { TextArea } from "@/components/ui/text-area";
import { TextField } from "@/components/ui/text-field";
import { TimePicker } from "@/components/ui/time-picker";

import { DEMO_OPTIONS, searchDemo } from "../demo-data";
import { Demo, DocSection, State } from "./doc";

const BANK_HOLIDAYS: ReadonlyMap<string, DayMarker> = new Map([
  ["2026-12-25", { label: "Bank holiday: Christmas Day", tone: "info" }],
  ["2026-12-28", { label: "Bank holiday: Boxing Day (substitute)", tone: "info" }],
  ["2026-11-05", { label: "Leave: Ada Lovelace", tone: "success" }],
]);

export function InputsSection() {
  const [salary, setSalary] = useState<number | null>(41700);
  const [hours, setHours] = useState<number | null>(37.5);
  const [time, setTime] = useState<string | null>("09:30");
  const [department, setDepartment] = useState<ComboboxOption | null>(null);
  const [remote, setRemote] = useState<ComboboxOption | null>(null);
  const [start, setStart] = useState<string | null>("2026-11-01");
  const [dob, setDob] = useState<string | null>(null);
  const [leave, setLeave] = useState<DateRange>({ start: "2026-11-02", end: "2026-11-06" });
  const [interview, setInterview] = useState<string | null>("2026-11-03T14:00");

  return (
    <DocSection
      id="inputs"
      title="Inputs"
      description="Fields have a label that floats up, a hint, an inline error and a clear button. Dates are typed or picked and shown as 1 Nov 2026; times are 24-hour."
    >
      <Demo
        title="Text field"
        note="The label is the field's name. It rests inside and floats on focus or when there is text."
      >
        <State label="Empty" className="w-64">
          <TextField label="Full name" />
        </State>
        <State label="Filled" className="w-64">
          <TextField label="Full name" defaultValue="Ada Lovelace" />
        </State>
        <State label="With hint" className="w-64">
          <TextField
            label="Work e-mail"
            type="email"
            hint="We send reminders here."
            startAdornment={<Icon icon={Mail} size={16} />}
          />
        </State>
        <State label="Error" className="w-64">
          <TextField
            label="National Insurance number"
            defaultValue="QQ 12"
            error="Enter 2 letters, 6 numbers and a letter, like QQ 12 34 56 C."
          />
        </State>
        <State label="Disabled" className="w-64">
          <TextField label="Employee number" defaultValue="EMP-0042" disabled />
        </State>
      </Demo>

      <Demo title="Search, text area and select">
        <State label="Search field" className="w-72">
          <SearchField label="Search people" shortcut="⌘K" />
        </State>
        <State label="Text area (grows as you type)" className="w-72">
          <TextArea
            label="Notes"
            defaultValue={"Prefers email.\nStarts on 1 Nov 2026.\nNeeds a laptop and a lanyard."}
            hint="Visible to Company Admins only."
          />
        </State>
        <State label="Select (the system picker on a phone)" className="w-64">
          <Select label="Contract type" defaultValue="permanent">
            <option value="permanent">Permanent</option>
            <option value="fixed">Fixed term</option>
            <option value="zero">Zero hours</option>
          </Select>
        </State>
        <State label="Select with an error" className="w-64">
          <Select
            label="Department"
            defaultValue=""
            placeholder="Choose a department"
            error="Choose a department."
          >
            <option value="ops">Operations</option>
            <option value="fin">Finance</option>
          </Select>
        </State>
      </Demo>

      <Demo
        title="Numbers, money, hours and time"
        note="Type £41,700 or use the arrow keys. It tidies the value when you leave the field."
      >
        <State label="Currency" className="w-56">
          <NumberField
            label="Salary"
            unit="currency"
            value={salary}
            onChange={setSalary}
            min={0}
            hint="Per year, before tax."
          />
        </State>
        <State label="Hours" className="w-56">
          <NumberField
            label="Contracted hours"
            unit="hours"
            value={hours}
            onChange={setHours}
            min={0}
            max={168}
          />
        </State>
        <State label="Time (24-hour)" className="w-56">
          <TimePicker label="Shift starts" value={time} onChange={setTime} />
        </State>
        <State label="Empty time with error" className="w-56">
          <TimePicker
            label="Shift ends"
            value={null}
            onChange={() => {}}
            error="Enter a time like 17:30."
          />
        </State>
      </Demo>

      <Demo
        title="Combobox"
        note="Pick from a long list by typing. Arrow keys move, Enter chooses, Esc closes. The second one searches as you type."
      >
        <State label="Fixed list" className="w-72">
          <Combobox
            label="Department"
            value={department}
            onChange={setDepartment}
            options={DEMO_OPTIONS}
          />
        </State>
        <State label="Searches as you type" className="w-72">
          <Combobox
            label="Find a department"
            value={remote}
            onChange={setRemote}
            loadOptions={searchDemo}
            hint="Type at least one letter."
          />
        </State>
      </Demo>

      <Demo
        title="Date picker"
        note="Type a date (1 Nov 2026, 1/11/26) or open the calendar. Bank holidays and leave show as dots. Alt + Down opens the calendar."
      >
        <State label="With a value" className="w-64">
          <DatePicker
            label="Start date"
            value={start}
            onChange={setStart}
            markers={BANK_HOLIDAYS}
          />
        </State>
        <State label="Empty, from 1 Jan 1950 to today" className="w-64">
          <DatePicker
            label="Date of birth"
            value={dob}
            onChange={setDob}
            min="1950-01-01"
            max="2026-11-01"
            hint="Enter it like 1 Nov 1990."
          />
        </State>
        <State label="Date range" className="w-full max-w-xl">
          <DateRangePicker
            legend="Leave dates"
            value={leave}
            onChange={setLeave}
            markers={BANK_HOLIDAYS}
          />
        </State>
        <State label="Date and time" className="w-full max-w-xl">
          <DateTimePicker
            legend="Interview date and time"
            value={interview}
            onChange={setInterview}
          />
        </State>
      </Demo>
    </DocSection>
  );
}
