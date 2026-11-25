// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/components/app/page-header", () => ({
  PageHeader: ({ title, description }: { title: string; description: string }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  ),
}));

import { ReceivedRemindersPage } from "./received-reminders-page";

describe("My documents reminders (ISS-13)", () => {
  it("shows only the header when the person may not read reminders", () => {
    render(<ReceivedRemindersPage reminders={null} />);
    expect(screen.getByRole("heading", { name: "My documents" })).toBeInTheDocument();
    expect(screen.queryByText("Reminders from HR")).not.toBeInTheDocument();
    expect(screen.queryByText("No reminders yet")).not.toBeInTheDocument();
  });

  it("shows the reminders panel when they may", () => {
    render(<ReceivedRemindersPage reminders={[]} />);
    expect(screen.getByText("Reminders from HR")).toBeInTheDocument();
    expect(screen.getByText("No reminders yet")).toBeInTheDocument();
  });
});
