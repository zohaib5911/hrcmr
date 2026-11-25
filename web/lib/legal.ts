import { brand } from "@brand";

export const LEGAL_DRAFT_NOTICE = "DRAFT — requires solicitor review";
export const LEGAL_DRAFT_DATE = "2026-11-12";
export interface LegalDocument {
  slug: string;
  title: string;
  introduction: string;
  sections: { title: string; paragraphs: string[] }[];
}

export const LEGAL_DOCUMENTS: readonly LegalDocument[] = [
  {
    slug: "terms",
    title: "Terms of service",
    introduction: `${brand.name} provides HR record keeping and sponsor-compliance tools for UK employers. These proposed business terms are a draft, not an approved agreement.`,
    sections: [
      {
        title: "Who provides the service",
        paragraphs: [
          "The contracting company's name, registration number, registered office and service address must be confirmed before these terms take effect. Use the contact form for questions about this draft.",
        ],
      },
      {
        title: "Your account and responsibilities",
        paragraphs: [
          "An authorised company administrator manages access and must keep account details accurate. Protect credentials, use multi-factor authentication where required, and remove access when someone leaves. Only upload information you are entitled to process; do not introduce malware, bypass access controls or use another company's records.",
          "You remain responsible for employment decisions, payroll, right-to-work checks and sponsor reporting. Reminders, rules, generated documents and AI suggestions need a competent person's review; they do not guarantee compliance or replace legal advice.",
        ],
      },
      {
        title: "Plans, payments and ending access",
        paragraphs: [
          "The free plan provides the access shown at sign-up. Paid annual and one-off 10-year plans have the price and period shown at checkout. Annual plans renew unless cancelled; cancelling stops the next renewal and access continues to the end of the paid term. The 10-year plan is a one-off purchase that does not renew. Payments are not refunded on cancellation; our cancellation terms page explains this.",
          "Failed payment can lead to read-only access after the payment grace period. We may restrict access to protect security or address abuse. Export your records before requesting account deletion; cancelling a paid plan does not itself delete your account.",
        ],
      },
      {
        title: "Rights and proposed contract limits",
        paragraphs: [
          "You retain rights in your uploaded records and give us permission to process them to provide the service. Our software and original resources remain ours or our licensors'. Confidential records must not be disclosed except as authorised or required by law.",
          "Service levels, changes to terms, suspension notices, liability limits, exclusions and governing law remain subject to solicitor approval. Nothing in this draft proposes excluding rights or liabilities that cannot lawfully be excluded. Do not rely on this draft as a signed contract.",
        ],
      },
    ],
  },
  {
    slug: "privacy",
    title: "Privacy notice",
    introduction:
      "This draft explains how information moves through the service. The employer normally controls its HR records; we process those records on its instructions. We separately control account administration, security, billing and public enquiries.",
    sections: [
      {
        title: "Information and purposes",
        paragraphs: [
          "Employer records may include employee and applicant contact details, employment and pay information, attendance, leave, health or absence records, right-to-work evidence, immigration documents, training and audit history. We use these to provide the employer's chosen HR functions, not to sell employee data.",
          "Account details, enquiry messages, billing references and security events help us administer accounts, respond to requests, collect payments and prevent abuse. Stripe receives payment information through its payment services. Do not send passports, medical records or bank details through the public contact form.",
        ],
      },
      {
        title: "Proposed lawful bases",
        paragraphs: [
          "For our own account and billing administration, the proposed bases are performance of a contract with the individual where applicable, legal obligations for required records, and legitimate interests in providing and securing a business service. Optional marketing tracking requires consent. The employer must identify its own bases, including any additional condition for health or other special-category data. The owner and solicitor must approve these bases and the legitimate-interest assessment before publication.",
        ],
      },
      {
        title: "Recipients and international access",
        paragraphs: [
          "The subprocessors page describes Railway, Cloudflare, Resend and optional Anthropic, with Stripe's separate controller role and Sentry's configuration status. Authorised support staff may access records for a recorded support reason, with an audit trail. We disclose information when legally required.",
          "Hosting regions, vendor contracting entities, international transfers and applicable safeguards must be confirmed in the signed DPA before launch. This draft does not promise that all processing stays in the UK.",
        ],
      },
      {
        title: "Retention and security",
        paragraphs: [
          "Access controls separate companies, sensitive fields are encrypted, uploaded files are scanned and changes are audited. No service can promise absolute security.",
          "Confirmed account deletion is scheduled after seven days and can be withdrawn before execution. Exports have expiring download links. Record retention depends on the employer's duties; routine retention purging is not yet fully implemented. Backup expiry and legal/accounting retention schedules require owner approval; do not treat this draft as a promise that every copy disappears on deletion day.",
        ],
      },
      {
        title: "Your choices and rights",
        paragraphs: [
          "Ask your employer first about records it controls. For records we control, use the complaints form to request access, correction, erasure, restriction or portability, to object, or to withdraw consent where it applies. We may need to verify identity, and rights depend on the circumstances. You can also complain to the Information Commissioner's Office at ico.org.uk. The owner's legal identity, privacy contact and final retention schedule must be supplied before this notice is approved.",
        ],
      },
    ],
  },
  {
    slug: "cookies",
    title: "Cookies and browser storage",
    introduction:
      "Only necessary storage is used by default. Reject all is as easy as Accept all. Use Cookie settings below or in the footer to change your choice.",
    sections: [
      {
        title: "First-party cookies used by the code",
        paragraphs: [
          "brand_session: HttpOnly sign-in token, expires after at most 14 days; the server also enforces an eight-hour idle timeout. brand_platform_session: separate HttpOnly platform-admin session, with the same maximum lifetime. brand_support_session: HttpOnly support-mode session, valid for 30 minutes. Deployment configuration may rename these three cookies.",
          "csrf: a browser-session security token used to protect API writes against forged requests. theme: remembers a requested light or dark appearance for 365 days; choosing System removes it. sidebar: remembers the app's expanded or collapsed sidebar for 365 days. These are security or requested interface preferences, not advertising cookies.",
        ],
      },
      {
        title: "Local storage is not a cookie",
        paragraphs: [
          "brand.cookieConsent stores {version, marketing, decidedAt} in this browser's localStorage. It has no automatic expiry; clearing browser storage or a change of consent version asks you again. brand.recentPages keeps at most eight app page addresses locally for the command palette, until you clear storage or they are replaced. Neither is used for advertising.",
        ],
      },
      {
        title: "Third-party services and optional marketing",
        paragraphs: [
          "Cloudflare Turnstile runs on protected forms to reduce automated abuse and receives browser/network signals. Cloudflare may use a cf_clearance cookie when clearance is enabled; this application does not set it itself. Stripe's hosted checkout and payment portal have their own storage policies; payment data is entered there.",
          "No Meta, Reddit or Google Ads pixels are installed in this version. Accepting marketing currently records a preference only. Any future marketing pixels must load only after consent on public marketing routes, never inside the app; their actual cookies and retention must be added to this policy before activation. Withdrawing consent stops future optional loading, but does not erase data already sent to a vendor. You can also delete cookies in your browser.",
        ],
      },
    ],
  },
  {
    slug: "dpa",
    title: "Data processing agreement",
    introduction:
      "Proposed schedule between the customer as controller and the service provider as processor. This draft requires completed party details and a signed agreement before reliance.",
    sections: [
      {
        title: "Scope and instructions",
        paragraphs: [
          "Subject matter: hosting and operating the customer's HR and sponsor-compliance workspace for the service term, followed by agreed return/deletion arrangements. Processing includes collecting, storing, organising, retrieving, exporting and deleting records on documented customer instructions, including the customer's use of the service.",
          "Data subjects include employees, workers, applicants, referees, emergency contacts and authorised users. Data includes identity and contact details, employment, salary, attendance, leave, recruitment, training, immigration evidence and audit records; health information may be included. The customer determines lawful purposes, accuracy, access and any special-category conditions.",
        ],
      },
      {
        title: "Confidentiality, security and assistance",
        paragraphs: [
          "The proposed processor obligations are to bind authorised personnel to confidentiality, restrict access, maintain appropriate technical and organisational measures, and assist with rights requests, breaches, impact assessments and regulator enquiries in light of the information available. Notify the controller of a personal-data breach without undue delay after becoming aware of it, and provide available information as it develops.",
          "Security measures include tenant isolation, role permissions, MFA for platform administrators, encryption of sensitive fields, private file storage, malware scanning, audit events and time-limited, recorded support access. Provide reasonable compliance evidence and allow proportionate audits under agreed confidentiality and security arrangements.",
        ],
      },
      {
        title: "Subprocessors and transfers",
        paragraphs: [
          "Use only authorised subprocessors under written obligations offering equivalent protection; remain responsible for their processing obligations. The customer must receive notice of proposed changes and an opportunity to object before the new processing starts. Notice periods and the objection process remain to be agreed.",
          "Do not make a restricted international transfer without the customer's documented authorisation and applicable safeguards. The final schedule must identify vendor entities, regions, transfer mechanisms and approved AI processing; those details are not yet verified for launch.",
        ],
      },
      {
        title: "Return, deletion and legal requirements",
        paragraphs: [
          "At the customer's choice, return or delete personal data at the end of service, including copies except where law requires retention. Agree an export window, backup expiry, secure deletion schedule and confirmation process before signing. The current account-deletion flow has a seven-day withdrawal period; it does not establish a complete contractual backup-retention schedule.",
          "Tell the customer if an instruction appears to infringe applicable data-protection law, and about a binding legal disclosure requirement unless law prohibits doing so. The final agreement must identify both parties, representatives, duration, security annex and commercial terms.",
        ],
      },
    ],
  },
  {
    slug: "subprocessors",
    title: "Subprocessors and service providers",
    introduction:
      "This is the architecture's vendor list, not a claim that every integration is active. Contracting entities, processing regions and transfer safeguards need owner verification before launch.",
    sections: [
      {
        title: "Railway — hosting",
        paragraphs: [
          "Hosts the deployed web/API services and the PostgreSQL and Redis infrastructure. Processes workspace records and operational data handled by those services. Local development uses local services instead. The selected production region and backup arrangements must be confirmed.",
        ],
      },
      {
        title: "Cloudflare — network, files and abuse protection",
        paragraphs: [
          "Provides DNS/proxy/security services, private R2 document storage and Turnstile bot protection when configured. Handles uploaded documents and network/security signals according to the enabled services. R2's configured endpoint and jurisdiction must be checked at deployment.",
        ],
      },
      {
        title: "Resend — transactional email",
        paragraphs: [
          "Receives recipient email addresses and message contents to deliver verification, account and HR notifications when its API key is configured. Development uses the local mail service. Avoid including unnecessary employee details in email.",
        ],
      },
      {
        title: "Anthropic — optional AI",
        paragraphs: [
          "Receives redacted or pseudonymised feature inputs for assisted drafting and matching when the server API key and feature switches enable AI. AI features are hidden otherwise and non-AI paths remain available. Customer approval, provider retention terms, region and transfer safeguards must be verified before enablement; do not assume redaction removes every personal detail.",
        ],
      },
      {
        title: "Sentry — planned error monitoring",
        paragraphs: [
          "The architecture includes Sentry configuration and permitted reporting endpoints, but this version has no active Sentry SDK instrumentation. Do not treat it as an active recipient. Verify scrubbing, sampled payloads, vendor terms and region before activation, and update this list.",
        ],
      },
      {
        title: "Stripe — independent controller for payments",
        paragraphs: [
          "Stripe handles checkout, payment processing and billing portal interactions when billing is configured. It receives billing/customer identifiers and payment data. For its payment, fraud-prevention and regulatory purposes it acts as an independent controller rather than our HR-data subprocessor; consult Stripe's privacy notice for its own processing.",
        ],
      },
    ],
  },
  {
    slug: "ai-policy",
    title: "AI policy",
    introduction:
      "AI assistance is optional and helps prepare material for a person to review. It must not make final employment or immigration decisions.",
    sections: [
      {
        title: "When AI is available",
        paragraphs: [
          "Server-side Anthropic integration is available only with the API key and applicable feature switches. Features are hidden without the key, and deterministic templates or other non-AI paths remain available. The Ask Mady chat feature is deferred.",
        ],
      },
      {
        title: "Inputs, outputs and human review",
        paragraphs: [
          "Inputs are redacted and pseudonymised before supported AI calls. Do not intentionally enter sensitive personal information in free text. The employer must authorise any processing and review generated text for accuracy, fairness and suitability. AI may invent facts, miss requirements or reproduce bias; verify sources and figures independently.",
          "Interaction records store operational metadata rather than prompts and answers. Do not infer that this controls Anthropic's retention; the owner must approve the provider's contractual retention and transfer terms. Report unsafe or discriminatory output through the complaints form.",
        ],
      },
    ],
  },
  {
    slug: "complaints",
    title: "Complaints",
    introduction:
      "Tell us what went wrong, which part of the service is affected and the outcome you would like. Use the contact form linked below; do not include passwords, identity documents or medical information.",
    sections: [
      {
        title: "How we handle your message",
        paragraphs: [
          "Your message goes to the platform support inbox for an authorised person to review. Our public contact target is a reply within one working day; this is an initial response target, not a guarantee that an investigation will finish then. If unresolved, reply with your reference and ask for further review.",
          "For a data protection complaint, choose that topic in the contact form. If it concerns your employer's HR records, contact the employer as controller too. You may complain to the ICO independently; using this form does not remove your rights.",
        ],
      },
    ],
  },
  {
    slug: "cancellation",
    title: "Cancellation terms",
    introduction:
      "How cancelling an annual or one-off 10-year plan works. This draft describes the implemented billing flow.",
    sections: [
      {
        title: "Annual plan",
        paragraphs: [
          "An authorised billing administrator can cancel in the app's billing page at any time. Cancelling stops the next renewal: the plan stays active until the end of the year already paid for, then ends and nothing more is charged. Payments already made are not refunded on cancellation.",
        ],
      },
      {
        title: "10-year plan",
        paragraphs: [
          "The 10-year plan is a single payment that does not renew, so there is nothing to cancel. It runs until its end date. Contact support for a disputed charge or exceptional issue. These proposed terms do not remove mandatory legal rights.",
        ],
      },
      {
        title: "Records and account deletion",
        paragraphs: [
          "Cancellation and account deletion are separate. Export records before requesting deletion. Confirmed deletion is scheduled seven days later and can be withdrawn before then. Final prices, tax wording, renewal notices and cancellation terms need solicitor and owner approval before paid launch.",
        ],
      },
    ],
  },
  {
    slug: "resources-disclaimer",
    title: "Resources disclaimer",
    introduction:
      "Guides, templates, calculators and the Sponsorship Job Checker are general information for UK employers. They are not legal, tax, payroll or immigration advice.",
    sections: [
      {
        title: "Check before acting",
        paragraphs: [
          "Results depend on your inputs, assumptions, the relevant UK jurisdiction and the date of the source data. Check the sources, validity dates and limitations shown with each resource. Rules change; a tool cannot assess every exception or personal circumstance.",
          "Adapt templates to the role and your organisation, have significant documents reviewed, and seek a qualified adviser where a decision affects someone's rights or immigration status. A checker result is not a Home Office decision or a guarantee of eligibility.",
        ],
      },
    ],
  },
  {
    slug: "register-terms",
    title: "Sponsor register terms",
    introduction:
      "The public sponsor directory presents information derived from the GOV.UK register of licensed sponsors. It is not an endorsement of an employer or a job offer.",
    sections: [
      {
        title: "Source and limits",
        paragraphs: [
          "Check the record's source and import date and consult the current official register before relying on it. Names and licence status can change between imports. A licence does not mean that an organisation has vacancies or will sponsor a particular applicant.",
          "Public information is used under the applicable Open Government Licence, except where otherwise stated. Official source: GOV.UK, Register of licensed sponsors: workers. Report an error through the contact form; we can investigate our display but cannot change the Home Office's source record. Do not use the directory for harassment, deceptive recruitment or unlawful personal-data collection.",
        ],
      },
    ],
  },
];

export function legalDocument(slug: string) {
  return LEGAL_DOCUMENTS.find((document) => document.slug === slug);
}
