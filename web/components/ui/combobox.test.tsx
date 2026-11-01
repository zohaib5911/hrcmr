// @vitest-environment jsdom
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Combobox, type ComboboxOption } from "./combobox";

const OPTIONS: ComboboxOption[] = [
  { value: "ops", label: "Operations" },
  { value: "fin", label: "Finance" },
  { value: "ppl", label: "People" },
];

function Harness(props: Partial<React.ComponentProps<typeof Combobox>>) {
  const [value, setValue] = useState<ComboboxOption | null>(null);
  return (
    <Combobox label="Department" value={value} onChange={setValue} options={OPTIONS} {...props} />
  );
}

describe("Combobox with a fixed list", () => {
  it("is a combobox that says whether its list is open", async () => {
    render(<Harness />);
    const box = screen.getByRole("combobox", { name: "Department" });
    expect(box).toHaveAttribute("aria-expanded", "false");
    expect(box).toHaveAttribute("aria-autocomplete", "list");
    await userEvent.click(box);
    expect(box).toHaveAttribute("aria-expanded", "true");
    expect(await screen.findByRole("listbox")).toBeInTheDocument();
  });

  it("filters as you type, ignoring case", async () => {
    render(<Harness />);
    await userEvent.type(screen.getByRole("combobox"), "FIN");
    const options = await screen.findAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual(["Finance"]);
  });

  it("highlights the first match, moves with the arrows, and chooses with Enter while focus stays put", async () => {
    render(<Harness />);
    const box = screen.getByRole("combobox");
    await userEvent.click(box);
    await userEvent.type(box, "o"); // Operations and People both contain an o
    expect(box).toHaveAttribute("aria-activedescendant", expect.stringMatching(/-option-0$/));
    await userEvent.keyboard("{ArrowDown}");
    expect(box).toHaveAttribute("aria-activedescendant", expect.stringMatching(/-option-1$/));
    expect(box).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    expect(box).toHaveValue("People");
    expect(box).toHaveAttribute("aria-expanded", "false");
  });

  it("does not run past the ends of the list", async () => {
    render(<Harness />);
    const box = screen.getByRole("combobox");
    await userEvent.click(box);
    await userEvent.keyboard("{ArrowUp}{ArrowUp}");
    expect(box).toHaveAttribute("aria-activedescendant", expect.stringMatching(/-option-0$/));
    await userEvent.keyboard("{ArrowDown}{ArrowDown}{ArrowDown}{ArrowDown}{ArrowDown}");
    expect(box).toHaveAttribute("aria-activedescendant", expect.stringMatching(/-option-2$/));
  });

  it("Escape closes the list and chooses nothing", async () => {
    render(<Harness />);
    const box = screen.getByRole("combobox");
    await userEvent.type(box, "fin");
    await userEvent.keyboard("{Escape}");
    expect(box).toHaveAttribute("aria-expanded", "false");
    expect(box).not.toHaveValue("Finance");
  });

  it("clicking an option chooses it", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("combobox"));
    await userEvent.click(await screen.findByRole("option", { name: "Finance" }));
    expect(screen.getByRole("combobox")).toHaveValue("Finance");
  });

  it("says when nothing matches", async () => {
    render(<Harness emptyText="Nothing here" />);
    await userEvent.type(screen.getByRole("combobox"), "zzz");
    expect((await screen.findAllByText("Nothing here")).length).toBeGreaterThan(0);
  });
});

describe("Combobox that searches", () => {
  function deferred<T>() {
    let resolve!: (value: T) => void;
    const promise = new Promise<T>((r) => (resolve = r));
    return { promise, resolve };
  }

  it("shows the answer to the LATEST search even if an older one answers last", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const first = deferred<ComboboxOption[]>();
    const second = deferred<ComboboxOption[]>();
    const queue = [first, second];
    const loadOptions = vi.fn(() => queue.shift()?.promise ?? Promise.resolve([]));
    render(<Harness options={undefined} loadOptions={loadOptions} debounceMs={10} />);

    const box = screen.getByRole("combobox");
    await userEvent.type(box, "a", { advanceTimers: vi.advanceTimersByTime });
    await act(() => vi.advanceTimersByTimeAsync(20));
    await userEvent.type(box, "b", { advanceTimers: vi.advanceTimersByTime });
    await act(() => vi.advanceTimersByTimeAsync(20));
    expect(loadOptions).toHaveBeenCalledTimes(2);

    // The newer search answers first, then the older one answers late.
    await act(async () => second.resolve([{ value: "new", label: "Answer to ab" }]));
    await act(async () => first.resolve([{ value: "old", label: "Answer to a" }]));

    expect(await screen.findByRole("option", { name: "Answer to ab" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Answer to a" })).not.toBeInTheDocument();
    vi.useRealTimers();
  });

  it("waits for the person to pause before searching (debounce)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const loadOptions = vi.fn(() => Promise.resolve([] as ComboboxOption[]));
    render(<Harness options={undefined} loadOptions={loadOptions} debounceMs={300} />);
    await userEvent.type(screen.getByRole("combobox"), "care", {
      advanceTimers: vi.advanceTimersByTime,
      delay: 50,
    });
    expect(loadOptions).not.toHaveBeenCalled();
    await act(() => vi.advanceTimersByTimeAsync(350));
    expect(loadOptions).toHaveBeenCalledTimes(1);
    expect(loadOptions).toHaveBeenCalledWith("care", expect.any(AbortSignal));
    vi.useRealTimers();
  });

  it("cancels the old search when a new one starts", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const signals: AbortSignal[] = [];
    const loadOptions = vi.fn((_query: string, signal: AbortSignal) => {
      signals.push(signal);
      return new Promise<ComboboxOption[]>(() => {});
    });
    render(<Harness options={undefined} loadOptions={loadOptions} debounceMs={10} />);
    const box = screen.getByRole("combobox");
    await userEvent.type(box, "a", { advanceTimers: vi.advanceTimersByTime });
    await act(() => vi.advanceTimersByTimeAsync(20));
    await userEvent.type(box, "b", { advanceTimers: vi.advanceTimersByTime });
    await act(() => vi.advanceTimersByTimeAsync(20));
    expect(signals).toHaveLength(2);
    expect(signals[0]?.aborted).toBe(true);
    expect(signals[1]?.aborted).toBe(false);
    vi.useRealTimers();
  });

  it("says so when the search fails", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const loadOptions = vi.fn(() => Promise.reject(new Error("network")));
    render(<Harness options={undefined} loadOptions={loadOptions} debounceMs={10} />);
    await userEvent.type(screen.getByRole("combobox"), "a", {
      advanceTimers: vi.advanceTimersByTime,
    });
    await act(() => vi.advanceTimersByTimeAsync(30));
    expect((await screen.findAllByText("Search failed. Try again.")).length).toBeGreaterThan(0);
    vi.useRealTimers();
  });
});
