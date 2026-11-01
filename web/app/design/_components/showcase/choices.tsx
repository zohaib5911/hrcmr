"use client";

import { CalendarDays, ClipboardList, Scale } from "lucide-react";
import { useState } from "react";

import { Checkbox } from "@/components/ui/checkbox";
import { Icon } from "@/components/ui/icon";
import { RadioCards } from "@/components/ui/radio-cards";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Toggle } from "@/components/ui/toggle";

import { Demo, DocSection, State } from "./doc";

export function ChoicesSection() {
  const [email, setEmail] = useState(true);
  const [some, setSome] = useState<boolean | "indeterminate">("indeterminate");
  const [role, setRole] = useState("employee");
  const [view, setView] = useState("calendar");
  const [range, setRange] = useState("week");
  const [icons, setIcons] = useState("calendar");

  return (
    <DocSection
      id="choices"
      title="Choices"
      description="Switches, checkboxes, radio cards, segmented controls and tabs. All of them work with the keyboard, and none rely on colour alone."
    >
      <Demo title="Toggle and checkbox">
        <State label="Toggle" className="w-80">
          <div className="flex flex-col gap-4">
            <Toggle
              label="E-mail me about expiring checks"
              description="Sent 28 days and 7 days before."
              checked={email}
              onCheckedChange={setEmail}
            />
            <Toggle label="Show archived employees" defaultChecked={false} />
            <Toggle label="Locked by your administrator" checked disabled />
          </div>
        </State>
        <State label="Checkbox" className="w-80">
          <div className="flex flex-col gap-4">
            <Checkbox
              label="Right to Work checked"
              description="Original documents seen in person or by share code."
              defaultChecked
            />
            <Checkbox
              label="Select all"
              checked={some}
              onCheckedChange={setSome}
              description="Some are chosen."
            />
            <Checkbox label="Not applicable" />
            <Checkbox label="Disabled" disabled />
          </div>
        </State>
      </Demo>

      <Demo
        title="Radio cards"
        note="Choose one, with a sentence for each option. Arrow keys move between cards."
      >
        <div className="w-full max-w-3xl">
          <RadioCards
            legend="Role"
            value={role}
            onValueChange={setRole}
            columns={3}
            options={[
              {
                value: "employee",
                title: "Employee",
                description: "Sees their own record, leave and payslips.",
              },
              {
                value: "manager",
                title: "Line manager",
                description: "Approves leave and sees their team.",
              },
              {
                value: "admin",
                title: "Company Admin",
                description: "Everything, including billing and access.",
              },
            ]}
          />
        </div>
      </Demo>

      <Demo
        title="Segmented control"
        note="A few views of the same thing. The highlight glides, or just fades when motion is reduced."
      >
        <State label="Text">
          <SegmentedControl
            label="Leave view"
            value={view}
            onValueChange={setView}
            segments={[
              { value: "calendar", label: "Calendar" },
              { value: "requests", label: "Requests" },
              { value: "balances", label: "Balances" },
            ]}
          />
        </State>
        <State label="Small">
          <SegmentedControl
            label="Range"
            size="sm"
            value={range}
            onValueChange={setRange}
            segments={[
              { value: "day", label: "Day" },
              { value: "week", label: "Week" },
              { value: "month", label: "Month" },
              { value: "custom", label: "Custom" },
            ]}
          />
        </State>
        <State label="Icons (named for screen readers)">
          <SegmentedControl
            label="Layout"
            value={icons}
            onValueChange={setIcons}
            segments={[
              {
                value: "calendar",
                ariaLabel: "Calendar",
                label: <Icon icon={CalendarDays} size={16} />,
              },
              { value: "list", ariaLabel: "List", label: <Icon icon={ClipboardList} size={16} /> },
              { value: "balance", ariaLabel: "Balances", label: <Icon icon={Scale} size={16} /> },
            ]}
          />
        </State>
      </Demo>

      <Demo
        title="Tabs"
        note="For the sections of one record. Left and right arrows move between them."
      >
        <div className="w-full max-w-2xl">
          <Tabs defaultValue="overview">
            <TabsList aria-label="Employee record">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="personal">Personal</TabsTrigger>
              <TabsTrigger value="employment">Employment</TabsTrigger>
              <TabsTrigger value="documents">Documents</TabsTrigger>
            </TabsList>
            <TabsContent value="overview" className="text-body text-label pt-4">
              The overview shows what needs attention first.
            </TabsContent>
            <TabsContent value="personal" className="text-body text-label pt-4">
              Name, contact details and emergency contacts.
            </TabsContent>
            <TabsContent value="employment" className="text-body text-label pt-4">
              Job, contract, location and reporting line.
            </TabsContent>
            <TabsContent value="documents" className="text-body text-label pt-4">
              Contracts, right to work evidence and certificates.
            </TabsContent>
          </Tabs>
        </div>
      </Demo>
    </DocSection>
  );
}
