import type { Metadata } from "next";

import { brand } from "@brand";

import { ProductShot } from "@/components/marketing/product-shot";
import { Band, CtaBand, Hero } from "@/components/marketing/sections";
import { SIGN_UP } from "@/lib/marketing-nav";

export const metadata: Metadata = {
  title: "Features",
  description: `What ${brand.name} does: people records, leave, attendance, rota, documents, learning, recruitment and sponsor compliance.`,
};

const MODULES = [
  {
    id: "people",
    shot: "people",
    title: "People",
    lead: "One record for every person, from the first contract to the last day.",
    points: [
      "Personal details, employment, pay and documents in one place.",
      "Sensitive details are encrypted and every change is logged.",
      "An organisation chart that follows the reporting lines.",
    ],
  },
  {
    id: "sponsor-compliance",
    shot: "compliance",
    title: "Sponsor compliance",
    lead: "See what needs attention across your licence, in one list.",
    points: [
      "Expiring visas and certificates of sponsorship, soonest first.",
      "Reporting duties with their deadlines and the evidence kept alongside.",
      "A pack of records ready for a Home Office visit.",
    ],
  },
  {
    id: "right-to-work",
    shot: "right-to-work",
    title: "Right to work",
    lead: "Record each check and be told before a follow-up is due.",
    points: [
      "Checks stored with the document copies and who made them.",
      "Follow-up dates reminded ahead of time.",
      "A full history for every person.",
    ],
  },
  {
    id: "leave",
    shot: "leave",
    title: "Leave",
    lead: "Requests, approvals and balances that allow for bank holidays.",
    points: [
      "Entitlement worked out for part-time and part-year staff.",
      "A team calendar so clashes show before you approve.",
      "Carry-over and year-end handled in one step.",
    ],
  },
  {
    id: "attendance",
    shot: "attendance",
    title: "Attendance and work log",
    lead: "Clock in and out, and keep the hours that matter for sponsored staff.",
    points: [
      "Clock in from a phone or a shared screen.",
      "Import hours from another system and review them in batches.",
      "A work log that supports weekly-hours checks.",
    ],
  },
  {
    id: "rota",
    shot: "rota",
    title: "Rota",
    lead: "Plan the week's shifts and publish them to the people working them.",
    points: [
      "Drag shifts across the week and see hours as you go.",
      "Rules flag rest-break and weekly-hours problems.",
      "Publishing notifies each person of their shifts.",
    ],
  },
  {
    id: "documents",
    shot: "documents",
    title: "Documents and policies",
    lead: "Company files with review dates, and proof who has read each policy.",
    points: [
      "Every file is virus-scanned on upload.",
      "Policies are assigned and acceptance is recorded.",
      "Review dates bring old documents back to the top.",
    ],
  },
  {
    id: "learning",
    shot: "learning",
    title: "Learning",
    lead: "Short compliance courses, with certificates you can check.",
    points: [
      "Assign a course to a person or a whole team.",
      "See who has finished and who is overdue.",
      "Certificates carry a code anyone can verify.",
    ],
  },
  {
    id: "recruitment",
    shot: "recruitment",
    title: "Recruitment",
    lead: "Post a role, collect applications and move people through stages.",
    points: [
      "A public careers page for your company.",
      "Candidates, interviews and notes together.",
      "A salary check for sponsored roles before you offer.",
    ],
  },
] as const;

export default function FeaturesPage() {
  return (
    <>
      <Hero
        eyebrow="Features"
        title="Everything in one calm place"
        lead="Each part works on its own and fits with the rest. Use only what your business needs."
      />
      {MODULES.map((module, index) => {
        return (
          <div key={module.id} id={module.id}>
            <Band
              tone={index % 2 === 0 ? "raised" : "page"}
              mediaFirst={index % 2 === 1}
              title={module.title}
              lead={module.lead}
              points={module.points}
              media={
                <ProductShot
                  name={module.shot}
                  alt={`The ${module.title.toLowerCase()} screen in ${brand.name}`}
                />
              }
            />
          </div>
        );
      })}
      <CtaBand
        title="Try it with your own team"
        lead="Start on the free plan. No card needed."
        actions={[{ label: SIGN_UP.label, href: SIGN_UP.href }]}
      />
    </>
  );
}
