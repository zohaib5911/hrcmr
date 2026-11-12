// @vitest-environment jsdom
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import Page from "@/app/(marketing)/resources/tools/skilled-worker-visa-checker/page";

const chief = { code: "1111", title: "Chief executives and senior officials" };
const nurse = { code: "2231", title: "Midwifery nurses" };
const manager = { code: "1150", title: "Managers and directors in retail and wholesale" };
let requests: Request[];

beforeEach(() => {
  requests = [];
  document.cookie = "csrf=test";
  vi.stubGlobal(
    "fetch",
    vi.fn(async (request: Request) => {
      requests.push(request);
      const url = new URL(request.url);
      if (url.pathname.endsWith("/9999")) {
        return Response.json(
          { error: { code: "NOT_FOUND", message: "We could not find that SOC code." } },
          { status: 404 },
        );
      }
      if (url.pathname.endsWith("/2231")) return Response.json(nurse);
      if (url.pathname.endsWith("/1150")) return Response.json(manager);
      return Response.json({ results: url.searchParams.get("q") === "nurse" ? [nurse] : [chief] });
    }),
  );
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("skilled worker visa checker page", () => {
  it("shows the occupation lookup privacy notice and sources", () => {
    render(<Page />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Skilled Worker visa checker",
    );
    expect(screen.getByText(/Only your SOC code or job title search is sent/)).toHaveTextContent(
      "Salary and personal answers stay in this page’s memory and are not saved or sent",
    );
    expect(within(screen.getByRole("table")).getAllByRole("link").length).toBe(4);
  });

  it("uses the public occupation lookup while keeping salary and personal answers local, then resets", async () => {
    const user = userEvent.setup();
    render(<Page />);
    await user.click(screen.getByRole("button", { name: "Check eligibility" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Choose an occupation");
    await user.type(screen.getByLabelText("SOC code or job title"), "chief executives");
    await user.click(await screen.findByRole("button", { name: /1111 Chief executives/ }));
    await user.type(screen.getByLabelText("Annual salary offered"), "90000");
    await user.selectOptions(screen.getByLabelText("Relevant PhD?"), "yes");
    await user.selectOptions(screen.getByLabelText("Is a partner applying as a dependant?"), "yes");
    await user.type(screen.getByLabelText("Dependent children applying"), "2");
    await user.click(screen.getByRole("button", { name: "Check eligibility" }));
    const result = screen.getByRole("region", { name: "Checker result" });
    expect(result).toHaveTextContent("Salary requirement met");
    expect(result).toHaveTextContent("B2");
    expect(requests).toHaveLength(1);
    expect(requests[0]?.method).toBe("GET");
    expect(new URL(requests[0]!.url).pathname).toBe("/api/v1/public/soc/search");
    expect(new URL(requests[0]!.url).search).toBe("?q=chief+executives");
    expect(await requests[0]!.text()).toBe("");
    await user.click(screen.getByRole("button", { name: "Reset answers" }));
    expect(screen.queryByText("Salary requirement met")).not.toBeInTheDocument();
  });

  it.each(["nurse", "2231"])(
    "allows a Table 3 nurse via %s and shows needs review with the official source",
    async (query) => {
      const user = userEvent.setup();
      render(<Page />);
      await user.type(screen.getByLabelText("SOC code or job title"), query);
      await user.click(await screen.findByRole("button", { name: "2231 Midwifery nurses" }));
      await user.type(screen.getByLabelText("Annual salary offered"), "40000");
      await user.click(screen.getByRole("button", { name: "Check eligibility" }));
      const result = screen.getByRole("region", { name: "Checker result" });
      expect(within(result).getByRole("heading", { name: "Needs review" })).toBeInTheDocument();
      expect(result).toHaveTextContent("2231 Midwifery nurses");
      expect(result).toHaveTextContent("option K");
      expect(result).not.toHaveTextContent("Not eligible");
      expect(within(result).queryByRole("table")).not.toBeInTheDocument();
      expect(
        within(result).getByRole("link", { name: /official Skilled Occupations/ }),
      ).toHaveAttribute(
        "href",
        "https://www.gov.uk/guidance/immigration-rules/immigration-rules-appendix-skilled-occupations",
      );
      expect(requests).toHaveLength(1);
      expect(requests[0]?.method).toBe("GET");
    },
  );

  it("distinguishes an invalid code from a valid Table 1a occupation unavailable to new applicants", async () => {
    const user = userEvent.setup();
    render(<Page />);
    const query = screen.getByLabelText("SOC code or job title");
    await user.type(query, "9999");
    expect(await screen.findByRole("status")).toHaveTextContent("We could not find that SOC code");
    expect(screen.queryByRole("list", { name: "Matching occupations" })).not.toBeInTheDocument();
    await user.clear(query);
    await user.type(query, "1150");
    await user.click(await screen.findByRole("button", { name: /1150 Managers/ }));
    await user.type(screen.getByLabelText("Annual salary offered"), "50000");
    await user.click(screen.getByRole("button", { name: "Check eligibility" }));
    const result = screen.getByRole("region", { name: "Checker result" });
    expect(result).toHaveTextContent("Not eligible on these answers");
    expect(result).toHaveTextContent("Table 1a");
    expect(result).not.toHaveTextContent("Needs review");
  });

  it("shows lookup failure without an eligibility verdict", async () => {
    vi.mocked(fetch).mockRejectedValue(new Error("offline"));
    const user = userEvent.setup();
    render(<Page />);
    await user.type(screen.getByLabelText("SOC code or job title"), "nurse");
    expect(await screen.findByRole("status")).toHaveTextContent("could not reach the server");
    expect(screen.queryByText("Not eligible on these answers")).not.toBeInTheDocument();
  });
});
