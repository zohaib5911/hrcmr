// @vitest-environment jsdom
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./button";
import { ConfirmDialog } from "./confirm-dialog";

function setup(props: Partial<React.ComponentProps<typeof ConfirmDialog>> = {}) {
  const onConfirm = props.onConfirm ?? vi.fn();
  render(
    <ConfirmDialog
      trigger={<Button>Delete</Button>}
      title="Delete Ada?"
      description="This cannot be undone."
      confirmLabel="Delete forever"
      onConfirm={onConfirm}
      {...props}
    />,
  );
  return { onConfirm };
}

describe("ConfirmDialog", () => {
  it("opens as an alert dialog with the question and starts on Cancel", async () => {
    setup();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Delete Ada?" });
    expect(dialog).toHaveAccessibleDescription("This cannot be undone.");
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  });

  it("runs the action and closes when confirmed", async () => {
    const { onConfirm } = setup();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await userEvent.click(await screen.findByRole("button", { name: "Delete forever" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
  });

  it("does nothing when cancelled", async () => {
    const { onConfirm } = setup();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("Escape cancels", async () => {
    const { onConfirm } = setup();
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    await screen.findByRole("alertdialog");
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(onConfirm).not.toHaveBeenCalled();
  });

  describe("when the name must be typed", () => {
    it("keeps the button off until the name matches exactly", async () => {
      const { onConfirm } = setup({ requireText: "Ada Lovelace", destructive: true });
      await userEvent.click(screen.getByRole("button", { name: "Delete" }));
      const confirm = await screen.findByRole("button", { name: "Delete forever" });
      const field = screen.getByLabelText("Type Ada Lovelace to confirm");
      expect(confirm).toBeDisabled();

      await userEvent.type(field, "Ada Lovelac");
      expect(confirm).toBeDisabled();
      await userEvent.type(field, "x");
      expect(confirm).toBeDisabled();
      await userEvent.clear(field);
      await userEvent.type(field, "ada lovelace");
      expect(confirm).toBeDisabled(); // case matters: it is a deliberate act
      await userEvent.clear(field);
      await userEvent.type(field, "Ada Lovelace");
      expect(confirm).toBeEnabled();
      await userEvent.click(confirm);
      expect(onConfirm).toHaveBeenCalledTimes(1);
    });

    it("Enter in the field does not confirm until the name matches", async () => {
      const { onConfirm } = setup({ requireText: "Ada Lovelace" });
      await userEvent.click(screen.getByRole("button", { name: "Delete" }));
      const field = await screen.findByLabelText("Type Ada Lovelace to confirm");
      await userEvent.type(field, "Ada{Enter}");
      expect(onConfirm).not.toHaveBeenCalled();
      await userEvent.type(field, " Lovelace{Enter}");
      expect(onConfirm).toHaveBeenCalledTimes(1);
    });

    it("forgets what was typed when it is closed and reopened", async () => {
      setup({ requireText: "Ada Lovelace" });
      await userEvent.click(screen.getByRole("button", { name: "Delete" }));
      await userEvent.type(
        await screen.findByLabelText("Type Ada Lovelace to confirm"),
        "Ada Lovelace",
      );
      await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
      await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
      await userEvent.click(screen.getByRole("button", { name: "Delete" }));
      expect(await screen.findByLabelText("Type Ada Lovelace to confirm")).toHaveValue("");
      expect(screen.getByRole("button", { name: "Delete forever" })).toBeDisabled();
    });
  });

  it("stays open while the action runs, then closes, and a second click does nothing", async () => {
    let finish!: () => void;
    const onConfirm = vi.fn(() => new Promise<void>((resolve) => (finish = resolve)));
    setup({ onConfirm });
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    const confirm = await screen.findByRole("button", { name: "Delete forever" });
    await userEvent.click(confirm);
    await userEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    finish();
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
  });
});
