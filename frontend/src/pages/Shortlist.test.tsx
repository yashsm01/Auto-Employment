import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { mockApi, renderPage } from "../test/utils";
import type { ShortlistItem } from "../api/pipeline";
import Shortlist from "./Shortlist";

function item(overrides: Partial<ShortlistItem> = {}): ShortlistItem {
  return {
    id: "a1",
    score: 87,
    title: "Junior Python Developer",
    company: "Freight Tech",
    city: "Auckland",
    salary: "NZ$75–85k",
    source: "Trade Me",
    matched_skills: ["Python", "FastAPI"],
    missing_skills: ["AWS"],
    reason: "Your API work matches their platform.",
    url: "https://example.invalid/job",
    is_example: false,
    required_covered: 0,
    required_total: 0,
    requirements_split: false,
    ...overrides,
  };
}

const analyst = () =>
  item({ id: "a2", score: 74, title: "Data Analyst", city: "Wellington", url: null });

function withItems(items: ShortlistItem[], decision?: () => { status?: number; body: unknown }) {
  let current = items;
  const routes: Record<string, (body: unknown) => { status?: number; body: unknown }> = {
    "GET /shortlist": () => ({ body: { items: current } }),
  };
  for (const entry of items) {
    routes[`POST /applications/${entry.id}/decision`] = (body) => {
      const reply = decision?.();
      if (reply) return reply;
      current = current.filter((candidate) => candidate.id !== entry.id);
      const action = (body as { action: string }).action;
      return { body: { id: entry.id, status: action === "approve" ? "tailoring" : "closed" } };
    };
  }
  return mockApi(routes);
}

describe("Shortlist", () => {
  it("shows why each job matched", async () => {
    withItems([item()]);
    renderPage(<Shortlist />);

    const card = (await screen.findByRole("heading", { name: "Junior Python Developer" })).closest(
      "article",
    )!;

    expect(within(card).getByText("87")).toBeInTheDocument();
    expect(within(card).getByText(/Freight Tech · Auckland · NZ\$75–85k/)).toBeInTheDocument();
    expect(within(card).getByText("FastAPI")).toBeInTheDocument();
    expect(within(card).getByText("Missing: AWS")).toBeInTheDocument();
    expect(within(card).getByText("Your API work matches their platform.")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: /view post/i })).toHaveAttribute(
      "href",
      "https://example.invalid/job",
    );
  });

  it("filters to high scores", async () => {
    withItems([item(), analyst()]);
    const user = userEvent.setup();
    renderPage(<Shortlist />);
    await screen.findByText("Data Analyst");

    await user.click(screen.getByRole("button", { name: "Score 80+" }));

    expect(screen.queryByText("Data Analyst")).not.toBeInTheDocument();
    expect(screen.getByText("Junior Python Developer")).toBeInTheDocument();
  });

  it("offers a filter for each city in the list", async () => {
    withItems([item(), analyst()]);
    const user = userEvent.setup();
    renderPage(<Shortlist />);
    await screen.findByText("Data Analyst");

    await user.click(screen.getByRole("button", { name: "Wellington" }));

    expect(screen.getByText("Data Analyst")).toBeInTheDocument();
    expect(screen.queryByText("Junior Python Developer")).not.toBeInTheDocument();
  });

  it("approves a job and removes it from the list", async () => {
    const calls = withItems([item(), analyst()]);
    const user = userEvent.setup();
    renderPage(<Shortlist />);

    await user.click(
      await screen.findByRole("button", { name: "Approve Junior Python Developer" }),
    );

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Approved Junior Python Developer",
    );
    expect(screen.queryByText("Junior Python Developer", { selector: "h2" })).toBeNull();
    expect(calls).toContainEqual({
      method: "POST",
      path: "/applications/a1/decision",
      body: { action: "approve" },
    });
  });

  it("skips a job", async () => {
    const calls = withItems([item()]);
    const user = userEvent.setup();
    renderPage(<Shortlist />);

    await user.click(await screen.findByRole("button", { name: "Skip Junior Python Developer" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Skipped Junior Python Developer");
    expect(calls).toContainEqual({
      method: "POST",
      path: "/applications/a1/decision",
      body: { action: "skip" },
    });
  });

  it("keeps the job and shows the error when a decision fails", async () => {
    withItems([item()], () => ({ status: 409, body: { detail: "Application is already closed" } }));
    const user = userEvent.setup();
    renderPage(<Shortlist />);

    await user.click(
      await screen.findByRole("button", { name: "Approve Junior Python Developer" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("Application is already closed");
    expect(screen.getByRole("heading", { name: "Junior Python Developer" })).toBeInTheDocument();
  });

  it("labels example data", async () => {
    withItems([item({ is_example: true })]);
    renderPage(<Shortlist />);

    expect(await screen.findByText("Example data")).toBeInTheDocument();
  });

  it("does not label real jobs as example data", async () => {
    withItems([item()]);
    renderPage(<Shortlist />);
    await screen.findByText("Junior Python Developer");

    expect(screen.queryByText("Example data")).not.toBeInTheDocument();
  });

  it("explains an empty shortlist", async () => {
    withItems([]);
    renderPage(<Shortlist />);

    expect(await screen.findByText(/no jobs on your shortlist/i)).toBeInTheDocument();
  });

  it("shows a load failure instead of an empty list", async () => {
    mockApi({ "GET /shortlist": () => ({ status: 500, body: { detail: "Database down" } }) });
    renderPage(<Shortlist />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Database down");
    expect(screen.queryByText(/no jobs on your shortlist/i)).not.toBeInTheDocument();
  });

  it("the shortlist chip shows and hides", async () => {
    withItems([
      item({ id: "a1", required_covered: 2, required_total: 3, requirements_split: true }),
      item({ id: "a2", title: "Data Analyst", required_covered: 1, required_total: 4, requirements_split: false }),
      item({ id: "a3", title: "Platform Lead", required_covered: 0, required_total: 0 }),
    ]);
    renderPage(<Shortlist />);

    const first = (await screen.findByRole("heading", { name: "Junior Python Developer" })).closest("article")!;
    expect(within(first).getByText("Skills: 2 of 3 required")).toBeInTheDocument();
    const second = screen.getByRole("heading", { name: "Data Analyst" }).closest("article")!;
    expect(within(second).getByText("Skills: 1 of 4 in the ad")).toBeInTheDocument();
    const third = screen.getByRole("heading", { name: "Platform Lead" }).closest("article")!;
    expect(within(third).queryByText(/Skills:/)).toBeNull();
  });
});
