import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { ApplicationDetail } from "../api/pipeline";
import { mockApi, renderPage } from "../test/utils";
import JobDetail from "./JobDetail";

function detail(overrides: Partial<ApplicationDetail> = {}): ApplicationDetail {
  return {
    id: "a1",
    status: "shortlisted",
    score: 87,
    similarity: 0.71,
    title: "Junior Python Developer",
    city: "Auckland",
    location: "Auckland CBD, Auckland",
    salary: "NZ$75–85k",
    source: "Trade Me",
    url: "https://example.invalid/job",
    description: "Build Python services.",
    matched_skills: ["Python"],
    missing_skills: ["AWS"],
    reason: "Your API work matches.",
    is_example: false,
    employer: {
      name: "Freight Tech",
      website: "https://example.invalid",
      phone: "09 000 0000",
      email: null,
      address: "12 Example St",
      about: "Builds freight software.",
      contacts: {},
      map_url: "https://www.google.com/maps/search/?api=1&query=12%20Example%20St",
      facts: [
        {
          field: "recent_news",
          value: "New tracking app",
          source: "tavily",
          confidence: "check",
          source_url: "https://news.example.invalid/a",
        },
      ],
    },
    timeline: [
      { type: "found", created_at: "2026-11-24T07:00:00Z" },
      { type: "shortlisted", created_at: "2026-11-24T07:01:00Z" },
    ],
    ...overrides,
  };
}

const page = (
  <Routes>
    <Route path="/jobs/:id" element={<JobDetail />} />
    <Route path="/shortlist" element={<p>Shortlist page</p>} />
  </Routes>
);

describe("JobDetail", () => {
  it("shows why the job matched", async () => {
    mockApi({ "GET /applications/a1": () => ({ body: detail() }) });
    renderPage(page, "/jobs/a1");

    expect(
      await screen.findByRole("heading", { name: "Junior Python Developer" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Your API work matches.")).toBeInTheDocument();
    expect(screen.getByText("Missing: AWS")).toBeInTheDocument();
    expect(screen.getByText("Build Python services.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /view original post/i })).toHaveAttribute(
      "href",
      "https://example.invalid/job",
    );
  });

  it("shows employer facts with their source and confidence", async () => {
    mockApi({ "GET /applications/a1": () => ({ body: detail() }) });
    const user = userEvent.setup();
    renderPage(page, "/jobs/a1");
    await screen.findByRole("heading", { name: "Junior Python Developer" });

    await user.click(screen.getByRole("tab", { name: "Employer" }));

    expect(screen.getByText("Builds freight software.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /open in google maps/i })).toHaveAttribute(
      "href",
      expect.stringContaining("google.com/maps"),
    );
    const fact = screen.getByText("New tracking app").closest("div")!.parentElement!;
    expect(within(fact).getByText("Tavily")).toBeInTheDocument();
    expect(within(fact).getByText("Check")).toBeInTheDocument();
  });

  it("does not link a company website that is not http", async () => {
    const base = detail();
    mockApi({
      "GET /applications/a1": () => ({
        body: detail({ employer: { ...base.employer, website: "javascript:alert(1)" } }),
      }),
    });
    const user = userEvent.setup();
    renderPage(page, "/jobs/a1");
    await screen.findByRole("heading", { name: "Junior Python Developer" });

    await user.click(screen.getByRole("tab", { name: "Employer" }));

    expect(screen.queryByRole("link", { name: "Company website" })).toBeNull();
  });

  it("does not link a map that is not http", async () => {
    const base = detail();
    mockApi({
      "GET /applications/a1": () => ({
        body: detail({ employer: { ...base.employer, map_url: "javascript:alert(1)" } }),
      }),
    });
    const user = userEvent.setup();
    renderPage(page, "/jobs/a1");
    await screen.findByRole("heading", { name: "Junior Python Developer" });

    await user.click(screen.getByRole("tab", { name: "Employer" }));

    expect(screen.queryByRole("link", { name: /open in google maps/i })).toBeNull();
  });

  it("shows the employer's contact details without a refresh button", async () => {
    const base = detail();
    mockApi({
      "GET /applications/a1": () => ({
        body: detail({
          employer: {
            ...base.employer,
            contacts: {
              phone: "09 111 1111",
              phone_source: "Google Maps",
              emails: ["hello@freight.example"],
              checked_at: "2026-11-25T20:00:00Z",
            },
          },
        }),
      }),
    });
    const user = userEvent.setup();
    renderPage(page, "/jobs/a1");
    await screen.findByRole("heading", { name: "Junior Python Developer" });

    await user.click(screen.getByRole("tab", { name: "Employer" }));

    const region = screen.getByRole("region", { name: "Contacts" });
    expect(within(region).getByRole("link", { name: "hello@freight.example" })).toHaveAttribute(
      "href",
      "mailto:hello@freight.example",
    );
    expect(within(region).getByText("Checked 26 Nov 2026")).toBeInTheDocument();
    expect(within(region).queryByRole("button")).toBeNull();
  });

  it("shows the contact history", async () => {
    mockApi({ "GET /applications/a1": () => ({ body: detail() }) });
    const user = userEvent.setup();
    renderPage(page, "/jobs/a1");
    await screen.findByRole("heading", { name: "Junior Python Developer" });

    await user.click(screen.getByRole("tab", { name: "Contact history" }));

    expect(screen.getByText("Found")).toBeInTheDocument();
    expect(screen.getByText("Shortlisted")).toBeInTheDocument();
  });

  it("approves a shortlisted job", async () => {
    let current = detail();
    const calls = mockApi({
      "GET /applications/a1": () => ({ body: current }),
      "POST /applications/a1/decision": () => {
        current = detail({ status: "tailoring" });
        return { body: { id: "a1", status: "tailoring" } };
      },
    });
    const user = userEvent.setup();
    renderPage(page, "/jobs/a1");

    await user.click(await screen.findByRole("button", { name: "Approve" }));

    expect(await screen.findByText("Waiting for resume tailoring")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(calls).toContainEqual({
      method: "POST",
      path: "/applications/a1/decision",
      body: { action: "approve" },
    });
  });

  it("shows deep search starting on the Preparation tab after approving", async () => {
    let current = detail();
    let prepStatus = "none";
    const prep = () => ({
      body: {
        application_id: "a1", status: prepStatus, pack: null, sources: [], notes: [],
        cost_nzd: null, finished_at: null, error: null, available: true,
        used_this_month: 0, monthly_limit: 30,
      },
    });
    mockApi({
      "GET /applications/a1": () => ({ body: current }),
      "GET /applications/a1/prep": prep,
      "POST /applications/a1/decision": () => {
        current = detail({ status: "tailoring" });
        prepStatus = "queued";
        return { body: { id: "a1", status: "tailoring" } };
      },
    });
    const user = userEvent.setup();
    renderPage(page, "/jobs/a1");
    await user.click(await screen.findByRole("tab", { name: "Preparation" }));
    await screen.findByRole("button", { name: "Run deep search" });

    await user.click(screen.getByRole("button", { name: "Approve" }));

    expect(
      await screen.findByText("Deep search is running. This takes about a minute."),
    ).toBeInTheDocument();
  });

  it("hides decisions once a job is closed", async () => {
    mockApi({ "GET /applications/a1": () => ({ body: detail({ status: "closed" }) }) });
    renderPage(page, "/jobs/a1");
    await screen.findByRole("heading", { name: "Junior Python Developer" });

    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Skip" })).toBeNull();
  });

  it("does not show a link when the job has none", async () => {
    mockApi({ "GET /applications/a1": () => ({ body: detail({ url: null }) }) });
    renderPage(page, "/jobs/a1");
    await screen.findByRole("heading", { name: "Junior Python Developer" });

    expect(screen.queryByRole("link", { name: /view original post/i })).toBeNull();
  });

  it("shows a load failure", async () => {
    mockApi({
      "GET /applications/a1": () => ({ status: 404, body: { detail: "Application not found" } }),
    });
    renderPage(page, "/jobs/a1");

    expect(await screen.findByRole("alert")).toHaveTextContent("Application not found");
  });
});
