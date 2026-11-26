import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { ReviewItem, TailoredResumeView } from "../api/resumes";
import { useOutbox } from "../hooks/useOutbox";
import { mockApi, renderPage } from "../test/utils";
import ResumeReview from "./ResumeReview";
import TailoredResume from "./TailoredResume";

function role(bullets: [string, string][]) {
  return {
    title: "Data Engineer",
    employer: "Example Retail Ltd",
    location: "Auckland",
    dates: "2022 - 2024",
    bullets: bullets.map(([id, text]) => ({ id, text })),
  };
}

function view(overrides: Partial<TailoredResumeView> = {}): TailoredResumeView {
  return {
    application_id: "a1",
    status: "ready",
    title: "Data Engineer",
    company: "Example Freight Tech",
    resume_id: "r1",
    base: {
      summary: "Developer with 2 years building internal tools.",
      roles: [role([["r0b0", "Built data pipelines."], ["r0b1", "Wrote SQL reports."]])],
      skills: ["Python", "SQL"],
      education: [],
      headline: "",
      interests: "",
      referees: "",
    },
    tailored: {
      summary: "Data engineer with 2 years building pipelines.",
      roles: [role([["r0b1", "Wrote SQL reports for finance."], ["r0b0", "Built data pipelines."]])],
      skills: ["SQL", "Python"],
      education: [],
      headline: "",
      interests: "",
      referees: "",
      cover_note: "Kia ora,\n\nI build pipelines.",
    },
    changed_ids: ["r0b1"],
    notes: ["Kept your original wording at Example Retail Ltd: the rewrite added AWS."],
    cover_note: "Kia ora,\n\nI build pipelines.",
    facts_used: ["Builds freight software."],
    ai_used: true,
    pdf_url: "/resumes/r1/pdf",
    error: null,
    ...overrides,
  };
}

const page = (
  <Routes>
    <Route path="/jobs/:id/resume" element={<TailoredResume />} />
  </Routes>
);

describe("TailoredResume", () => {
  it("shows the original and tailored versions with changes marked", async () => {
    mockApi({ "GET /applications/a1/resume": () => ({ body: view() }) });
    renderPage(page, "/jobs/a1/resume");

    const original = await screen.findByRole("region", { name: "Your original resume" });
    const tailored = screen.getByRole("region", { name: "Tailored for this job" });

    expect(within(original).getByText("Wrote SQL reports.")).toBeInTheDocument();
    const changed = within(tailored).getByText("Wrote SQL reports for finance.");
    expect(changed.closest("li")).toHaveAttribute("data-changed", "true");
    expect(within(tailored).getByText("Built data pipelines.").closest("li")).toHaveAttribute(
      "data-changed",
      "false",
    );
    expect(within(tailored).getByText(/Example Retail Ltd/)).toBeInTheDocument();
    expect(within(tailored).getByText(/Data engineer with 2 years/)).toHaveAttribute(
      "data-changed",
      "true",
    );
    expect(within(original).getByText(/Developer with 2 years/)).toHaveAttribute(
      "data-changed",
      "false",
    );
  });

  it("explains what the fact check kept and which employer facts were used", async () => {
    mockApi({ "GET /applications/a1/resume": () => ({ body: view() }) });
    renderPage(page, "/jobs/a1/resume");

    const check = await screen.findByRole("region", { name: "Fact check" });

    expect(within(check).getByText(/the rewrite added AWS/)).toBeInTheDocument();
    expect(within(check).getByText("Builds freight software.")).toBeInTheDocument();
  });

  it("offers the PDF", async () => {
    mockApi({ "GET /applications/a1/resume": () => ({ body: view() }) });
    renderPage(page, "/jobs/a1/resume");

    expect(await screen.findByRole("link", { name: "Download PDF" })).toHaveAttribute(
      "href",
      expect.stringMatching(/\/resumes\/r1\/pdf$/),
    );
  });

  it("saves an edited cover note", async () => {
    const calls = mockApi({
      "GET /applications/a1/resume": () => ({ body: view() }),
      "PUT /applications/a1/resume": (body) => ({
        body: view({ cover_note: (body as { cover_note: string }).cover_note }),
      }),
    });
    const user = userEvent.setup();
    renderPage(page, "/jobs/a1/resume");
    const note = await screen.findByLabelText("Cover note");

    await user.clear(note);
    await user.type(note, "Kia ora, edited.");
    await user.click(screen.getByRole("button", { name: "Save cover note" }));

    expect(await screen.findByText("Cover note saved.")).toBeInTheDocument();
    expect(calls).toContainEqual({
      method: "PUT",
      path: "/applications/a1/resume",
      body: { cover_note: "Kia ora, edited." },
    });
  });

  it("approves the resume for sending", async () => {
    let current = view();
    const calls = mockApi({
      "GET /applications/a1/resume": () => ({ body: current }),
      "POST /applications/a1/resume-decision": () => {
        current = view({ status: "approved" });
        return { body: { id: "a1", status: "approved" } };
      },
    });
    const user = userEvent.setup();
    renderPage(page, "/jobs/a1/resume");

    await user.click(await screen.findByRole("button", { name: "Approve" }));

    expect(await screen.findByRole("status")).toHaveTextContent(/Approved\. Send it from the Outbox\./);
    expect(screen.getByRole("link", { name: "Outbox" })).toHaveAttribute("href", "/outbox");
    expect(calls).toContainEqual({
      method: "POST",
      path: "/applications/a1/resume-decision",
      body: { action: "approve" },
    });
    expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  });

  it("refreshes the Outbox after approving, so its count is current", async () => {
    let current = view();
    const calls = mockApi({
      "GET /applications/a1/resume": () => ({ body: current }),
      "GET /outbox": () => ({
        body: {
          sending_enabled: false, reading_enabled: false, daily_limit: 15, sent_today: 0,
          to_send: [], queued: [], failed: [], waiting: [], replied: [], drafts: [],
        },
      }),
      "POST /applications/a1/resume-decision": () => {
        current = view({ status: "approved" });
        return { body: { id: "a1", status: "approved" } };
      },
    });
    function OutboxProbe() {
      useOutbox();
      return null;
    }
    const user = userEvent.setup();
    renderPage(
      <>
        <OutboxProbe />
        {page}
      </>,
      "/jobs/a1/resume",
    );
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    await screen.findByRole("status");

    await waitFor(() =>
      expect(calls.filter((c) => c.method === "GET" && c.path === "/outbox").length).toBe(2),
    );
  });

  it("rejects the resume", async () => {
    const calls = mockApi({
      "GET /applications/a1/resume": () => ({ body: view() }),
      "POST /applications/a1/resume-decision": () => ({ body: { id: "a1", status: "closed" } }),
    });
    const user = userEvent.setup();
    renderPage(page, "/jobs/a1/resume");

    await user.click(await screen.findByRole("button", { name: "Reject" }));

    expect(calls).toContainEqual({
      method: "POST",
      path: "/applications/a1/resume-decision",
      body: { action: "reject" },
    });
  });

  it("shows progress while tailoring and the error if it failed", async () => {
    mockApi({
      "GET /applications/a1/resume": () => ({
        body: view({
          status: "tailoring",
          resume_id: null,
          tailored: null,
          base: null,
          pdf_url: null,
          error: "BadRequest: Upload your resume first, on My resume profile.",
        }),
      }),
    });
    renderPage(page, "/jobs/a1/resume");

    expect(await screen.findByRole("alert")).toHaveTextContent("Upload your resume first");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("regenerates a new version", async () => {
    const calls = mockApi({
      "GET /applications/a1/resume": () => ({ body: view() }),
      "POST /applications/a1/tailor": () => ({ body: { id: "a1", status: "tailoring" } }),
    });
    const user = userEvent.setup();
    renderPage(page, "/jobs/a1/resume");

    await user.click(await screen.findByRole("button", { name: "Regenerate" }));

    expect(calls.some((call) => call.method === "POST" && call.path === "/applications/a1/tailor")).toBe(
      true,
    );
  });

  it("the tailored page offers Download Word", async () => {
    mockApi({
      "GET /applications/a1/resume": () => ({
        body: view({ docx_url: "/resumes/r1/docx" }),
      }),
    });
    renderPage(page, "/jobs/a1/resume");

    expect(await screen.findByRole("link", { name: "Download Word" })).toHaveAttribute(
      "href",
      expect.stringMatching(/\/resumes\/r1\/docx$/),
    );
  });

  it("I have this posts have, shows the result, and Undo posts null", async () => {
    const skillRow = (status: "missing" | "added", evidence: string) => ({
      name: "dbt",
      status,
      evidence,
      matched_as: null,
    });
    let current = view({
      coverage: {
        required: [],
        preferred: [skillRow("missing", "")],
        split: false,
        required_text: "0 of 0",
        preferred_text: "0 of 1",
      },
    });
    const calls = mockApi({
      "GET /applications/a1/resume": () => ({ body: current }),
      "POST /skills/decision": (body) => {
        const decision = (body as { decision: string | null }).decision;
        current = view({
          coverage: {
            required: [],
            preferred: [decision === "have" ? skillRow("added", "Added to your CV.") : skillRow("missing", "")],
            split: false,
            required_text: "0 of 0",
            preferred_text: "0 of 1",
          },
        });
        return { body: { ok: true } };
      },
    });
    const user = userEvent.setup();
    renderPage(page, "/jobs/a1/resume");

    await user.click(await screen.findByRole("button", { name: "I have this: dbt" }));

    expect(await screen.findByText("Added dbt to your CV.")).toBeInTheDocument();
    expect(calls).toContainEqual({
      method: "POST",
      path: "/skills/decision",
      body: { skill: "dbt", decision: "have" },
    });
    await user.click(await screen.findByRole("button", { name: "Undo: dbt" }));
    expect(await screen.findByText("Undone.")).toBeInTheDocument();
    expect(calls).toContainEqual({
      method: "POST",
      path: "/skills/decision",
      body: { skill: "dbt", decision: null },
    });
  });

  it("says when AI was not used", async () => {
    mockApi({
      "GET /applications/a1/resume": () => ({
        body: view({ ai_used: false, tailored: null, changed_ids: [], notes: [] }),
      }),
    });
    renderPage(page, "/jobs/a1/resume");

    expect(await screen.findByText(/AI is not connected/)).toBeInTheDocument();
  });
});

describe("ResumeReview", () => {
  function item(overrides: Partial<ReviewItem> = {}): ReviewItem {
    return {
      application_id: "a1",
      status: "ready",
      title: "Data Engineer",
      company: "Example Freight Tech",
      resume_id: "r1",
      error: null,
      ...overrides,
    };
  }

  it("lists resumes to review and ones still being tailored", async () => {
    mockApi({
      "GET /resume-review": () => ({
        body: {
          items: [
            item(),
            item({ application_id: "a2", status: "tailoring", title: "Analyst", resume_id: null }),
          ],
        },
      }),
    });
    renderPage(<ResumeReview />);

    const ready = (await screen.findByText("Data Engineer")).closest("article")!;
    expect(within(ready).getByRole("link", { name: /review/i })).toHaveAttribute(
      "href",
      "/jobs/a1/resume",
    );
    const pending = screen.getByText("Analyst").closest("article")!;
    expect(within(pending).getByText(/Tailoring/)).toBeInTheDocument();
  });

  it("explains an empty list", async () => {
    mockApi({ "GET /resume-review": () => ({ body: { items: [] } }) });
    renderPage(<ResumeReview />);

    expect(await screen.findByText(/No resumes to review/)).toBeInTheDocument();
  });
});
