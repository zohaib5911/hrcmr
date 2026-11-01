// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button, IconButton } from "./button";

describe("Button", () => {
  it("is a real button that does not submit a form by accident", () => {
    render(<Button>Save</Button>);
    expect(screen.getByRole("button", { name: "Save" })).toHaveAttribute("type", "button");
  });

  it("calls onClick", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Save</Button>);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  it("while loading, ignores clicks, says it is busy, and keeps its name and keyboard focus", async () => {
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Save
      </Button>,
    );
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toHaveAttribute("aria-busy", "true");
    expect(button).toHaveAttribute("aria-disabled", "true");
    // Not `disabled`: a busy button must stay focusable so keyboard focus is not thrown away.
    expect(button).not.toBeDisabled();
    await userEvent.click(button);
    button.focus();
    expect(button).toHaveFocus();
    expect(onClick).not.toHaveBeenCalled();
  });

  it("keeps its label in place while loading, so it keeps its width", () => {
    render(<Button loading>Save changes</Button>);
    const label = screen.getByText("Save changes");
    expect(label).toBeInTheDocument();
    expect(label).toHaveClass("opacity-0");
  });

  it("can give its look to a link", () => {
    render(
      <Button asChild variant="tinted">
        <a href="/somewhere">Go</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Go" });
    expect(link).toHaveAttribute("href", "/somewhere");
    expect(link.className).toContain("rounded-control");
  });

  it("keeps text size and text colour together (they used to cancel each other out)", () => {
    render(<Button variant="filled">Save</Button>);
    const button = screen.getByRole("button", { name: "Save" });
    expect(button).toHaveClass("text-body");
    expect(button).toHaveClass("text-on-accent");
  });
});

describe("IconButton", () => {
  it("is named by its label, since it has no visible text", () => {
    render(
      <IconButton label="Delete">
        <svg />
      </IconButton>,
    );
    expect(screen.getByRole("button", { name: "Delete" })).toBeInTheDocument();
  });
});
