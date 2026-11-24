import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PrepView } from "../api/prep";
import { mockApi, renderPage } from "../test/utils";
import PreparationTab from "./PreparationTab";

function view(overrides: Partial<PrepView> = {}): PrepView {
  return {
    application_id: "a1",
    status: "done",
    pack: {
      evidence: [
        { requirement: "Python", evidence: "Built pipelines in Python.", status: "matched" },
        { requirement: "Kubernetes", evidence: null, status: "gap" },
      ],
      interview_stages: ["Recruiter call", "Technical interview"],
      pay: { text: "NZ$85k–100k for this role", source_ids: ["s3"] },
      employer: [{ text: "Builds port software", source_ids: ["s2"] }],
      questions: ["How does the team deploy?"],
      brush_up: ["Kubernetes"],
      practical: [{ text: "Office in Dunedin", source_ids: ["s2"] }],
      tips: ["Stress your pipeline work."],
      unknowns: ["Referee process"],
      could_not_verify: ["Founded in 1999"],
    },
    sources: [
      { id: "s1", title: "Job post", url: null, kind: "job_post" },
      { id: "s2", title: "Example website", url: "https://example.co.nz", kind: "website" },
      { id: "s3", title: "Pay guide", url: "https://pay.example.org", kind: "search" },
    ],
    notes: ["Stopped reading after 6 pages."],
    cost_nzd: 0.07,
    finished_at: "2026-11-24T08:00:00Z",
    error: null,
    available: true,
    used_this_month: 3,
    monthly_limit: 30,
    ...overrides,
  };
}

describe("PreparationTab", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows every section of the pack with sources, cost and usage", async () => {
    mockApi({ "GET /applications/a1/prep": () => ({ body: view() }) });
    renderPage(<PreparationTab applicationId="a1" />);

    const evidence = await screen.findByRole("region", {
      name: "Your evidence for each requirement",
    });
    expect(within(evidence).getByText("Built pipelines in Python.")).toBeInTheDocument();
    expect(within(evidence).getByText(/Gap/)).toBeInTheDocument();
    for (const name of [
      "Likely interview stages (unconfirmed)",
      "Pay range",
      "About the employer",
      "Questions to ask",
      "Things to brush up on",
      "Practical details",
      "Application tips",
      "Unknowns",
      "Could not verify",
      "Sources",
    ]) {
      expect(screen.getByRole("region", { name })).toBeInTheDocument();
    }
    const employer = screen.getByRole("region", { name: "About the employer" });
    const mark = within(employer).getByRole("link", { name: "[s2]" });
    expect(mark).toHaveAttribute("href", "https://example.co.nz");
    expect(mark).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByText(/This run cost NZ\$0\.07/)).toBeInTheDocument();
    expect(screen.getByText(/3 of 30 deep searches used this month/)).toBeInTheDocument();
    expect(screen.getByText("Stopped reading after 6 pages.")).toBeInTheDocument();
  });

  it("shows the source quote under employer lines and a directions link", async () => {
    const pack = {
      ...view().pack!,
      employer: [
        { text: "Builds port software", source_ids: ["s2"], quote: "we build port software" },
      ],
      directions_url: "https://www.google.com/maps/dir/?api=1&destination=Dunedin",
    };
    mockApi({ "GET /applications/a1/prep": () => ({ body: view({ pack }) }) });
    renderPage(<PreparationTab applicationId="a1" />);

    const employer = await screen.findByRole("region", { name: "About the employer" });
    expect(within(employer).getByText("“we build port software”")).toBeInTheDocument();
    const practical = screen.getByRole("region", { name: "Practical details" });
    expect(within(practical).getByRole("link", { name: "Directions on Google Maps" })).toHaveAttribute(
      "href",
      "https://www.google.com/maps/dir/?api=1&destination=Dunedin",
    );
  });

  it("hides Could not verify when everything was verified", async () => {
    const pack = { ...view().pack!, could_not_verify: [] };
    mockApi({ "GET /applications/a1/prep": () => ({ body: view({ pack }) }) });
    renderPage(<PreparationTab applicationId="a1" />);

    await screen.findByRole("region", { name: "About the employer" });
    expect(screen.queryByRole("region", { name: "Could not verify" })).not.toBeInTheDocument();
  });

  it("shows progress while running", async () => {
    mockApi({
      "GET /applications/a1/prep": () => ({ body: view({ status: "running", pack: null }) }),
    });
    renderPage(<PreparationTab applicationId="a1" />);

    expect(
      await screen.findByText("Deep search is running. This takes about a minute."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run deep search" })).not.toBeInTheDocument();
  });

  it("runs deep search with the extra details", async () => {
    const calls = mockApi({
      "GET /applications/a1/prep": () => ({ body: view({ status: "none", pack: null }) }),
      "POST /applications/a1/prep": () => ({ body: view({ status: "queued", pack: null }) }),
    });
    renderPage(<PreparationTab applicationId="a1" />);

    await userEvent.type(
      await screen.findByLabelText("Extra details (a link or text)"),
      "Team uses Go.",
    );
    await userEvent.click(screen.getByRole("button", { name: "Run deep search" }));

    await waitFor(() =>
      expect(calls.find((c) => c.method === "POST")?.body).toEqual({ extra: "Team uses Go." }),
    );
  });

  it("shows the error and tries again after a failed run", async () => {
    const calls = mockApi({
      "GET /applications/a1/prep": () => ({
        body: view({ status: "failed", pack: null, error: "Upload your resume first." }),
      }),
      "POST /applications/a1/prep": () => ({ body: view({ status: "queued", pack: null }) }),
    });
    renderPage(<PreparationTab applicationId="a1" />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Upload your resume first.");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    await waitFor(() =>
      expect(calls.find((c) => c.method === "POST")?.body).toEqual({ extra: null }),
    );
  });

  it("explains that deep search needs a Claude key", async () => {
    mockApi({
      "GET /applications/a1/prep": () => ({
        body: view({ status: "none", pack: null, available: false }),
      }),
    });
    renderPage(<PreparationTab applicationId="a1" />);

    expect(
      await screen.findByText("Deep search needs a Claude key in backend/.env."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run deep search" })).not.toBeInTheDocument();
  });
});
