import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OutboxItem, OutboxView } from "../api/outbox";
import { mockApi, renderPage } from "../test/utils";
import Outbox from "./Outbox";

function view(overrides: Partial<OutboxView> = {}): OutboxView {
  return {
    sending_enabled: false,
    reading_enabled: true,
    daily_limit: 15,
    sent_today: 2,
    to_send: [
      {
        application_id: "a1",
        title: "Data Engineer",
        company: "Example Freight Tech",
        application_kind: "advert",
        suggested_to: "jobs@example.co.nz",
        job_url: "https://example.co.nz/jobs/1",
        pdf_url: "/resumes/r1/pdf",
        cover_note: "Kia ora,\n\nI'm applying…",
      },
    ],
    queued: [],
    failed: [],
    waiting: [],
    replied: [],
    drafts: [],
    ...overrides,
  };
}

const findCall = (calls: { method: string; path: string; body: unknown }[], path: string) =>
  calls.find((call) => call.method !== "GET" && call.path === path);

describe("Outbox", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("explains that sending is off and queues an email to the suggested address", async () => {
    const calls = mockApi({
      "GET /outbox": () => ({ body: view() }),
      "GET /outbox/contacts": () => ({ body: { rows: [] } }),
      "POST /applications/a1/send": () => ({ body: view({ to_send: [] }) }),
    });
    renderPage(<Outbox />);

    expect(await screen.findByText(/Email sending is off/)).toBeInTheDocument();
    expect(screen.getByText("2 of 15 emails sent today")).toBeInTheDocument();
    const item = screen.getByRole("article", { name: /Data Engineer/ });
    expect(within(item).getByLabelText("Send to")).toHaveValue("jobs@example.co.nz");
    expect(within(item).getByRole("link", { name: "Download PDF" })).toHaveAttribute(
      "href",
      expect.stringMatching(/\/resumes\/r1\/pdf$/),
    );
    await userEvent.click(within(item).getByRole("button", { name: "Queue email" }));

    await waitFor(() =>
      expect(findCall(calls, "/applications/a1/send")?.body).toEqual({
        to: "jobs@example.co.nz",
      }),
    );
  });

  it("records an application made on the job site", async () => {
    const calls = mockApi({
      "GET /outbox": () => ({ body: view() }),
      "GET /outbox/contacts": () => ({ body: { rows: [] } }),
      "POST /applications/a1/applied": () => ({ body: view({ to_send: [] }) }),
    });
    renderPage(<Outbox />);

    await userEvent.click(await screen.findByRole("button", { name: "I applied on the job site" }));

    await waitFor(() => expect(findCall(calls, "/applications/a1/applied")).toBeTruthy());
  });

  it("cancels a queued email and retries a failed one", async () => {
    const email = {
      id: "o1",
      application_id: "a1",
      title: "Data Engineer",
      company: "Example Freight Tech",
      kind: "application" as const,
      application_kind: "advert" as const,
      to: "jobs@example.co.nz",
      subject: "Application for Data Engineer",
      scheduled_at: "2026-11-25T08:00:00Z",
      attempts: 0,
      error: null,
    };
    const current = view({
      to_send: [],
      queued: [email],
      failed: [{ ...email, id: "o2", attempts: 3, error: "email: sending failed (OSError)" }],
    });
    const calls = mockApi({
      "GET /outbox": () => ({ body: current }),
      "GET /outbox/contacts": () => ({ body: { rows: [] } }),
      "POST /outbox/o1/cancel": () => ({ body: current }),
      "POST /outbox/o2/retry": () => ({ body: current }),
    });
    renderPage(<Outbox />);

    const queued = await screen.findByRole("region", { name: "Queued" });
    await userEvent.click(within(queued).getByRole("button", { name: "Cancel" }));
    const failed = screen.getByRole("region", { name: "Failed" });
    expect(within(failed).getByText(/sending failed/)).toBeInTheDocument();
    await userEvent.click(within(failed).getByRole("button", { name: "Try again" }));

    await waitFor(() => expect(findCall(calls, "/outbox/o1/cancel")).toBeTruthy());
    await waitFor(() => expect(findCall(calls, "/outbox/o2/retry")).toBeTruthy());
  });

  it("shows follow-ups that are due and records what happened", async () => {
    const current = view({
      to_send: [],
      waiting: [
        {
          application_id: "a2",
          title: "Analyst",
          company: "Example Health",
          apply_method: "manual",
          application_kind: "advert",
          to: null,
          applied_at: "2026-11-17T08:00:00Z",
          follow_ups: 0,
          next_follow_up: "2026-11-24",
          follow_up_due: true,
          job_url: null,
        },
      ],
    });
    const calls = mockApi({
      "GET /outbox": () => ({ body: current }),
      "GET /outbox/contacts": () => ({ body: { rows: [] } }),
      "POST /applications/a2/outcome": () => ({ body: current }),
    });
    renderPage(<Outbox />);

    const waiting = await screen.findByRole("region", { name: "Waiting for a reply" });
    expect(within(waiting).getByText("Follow-up due")).toBeInTheDocument();
    expect(within(waiting).getByText(/Applied on the job site/)).toBeInTheDocument();
    await userEvent.click(within(waiting).getByRole("button", { name: "I followed up" }));
    await waitFor(() =>
      expect(findCall(calls, "/applications/a2/outcome")?.body).toEqual({ action: "followed_up" }),
    );
    await userEvent.click(within(waiting).getByRole("button", { name: "They replied" }));
    await waitFor(() =>
      expect(
        calls.filter((c) => c.path === "/applications/a2/outcome").map((c) => c.body),
      ).toContainEqual({ action: "replied" }),
    );
  });

  it("shows the AI call result and emails the resume to the address given", async () => {
    const current = view({
      to_send: [],
      waiting: [
        {
          application_id: "a3",
          title: "Data Engineer",
          company: "Example Freight Tech",
          apply_method: "email",
          application_kind: "advert",
          to: "jobs@example.co.nz",
          applied_at: "2026-11-03T08:00:00Z",
          follow_ups: 2,
          next_follow_up: null,
          follow_up_due: false,
          job_url: null,
          call_status: "done",
          captured_email: "hr@freight.example",
        },
      ],
    });
    const calls = mockApi({
      "GET /outbox": () => ({ body: current }),
      "GET /outbox/contacts": () => ({ body: { rows: [] } }),
      "POST /applications/a3/send-after-call": () => ({ body: current }),
    });
    renderPage(<Outbox />);

    const waiting = await screen.findByRole("region", { name: "Waiting for a reply" });
    expect(within(waiting).getByText(/AI call: completed/)).toBeInTheDocument();
    await userEvent.click(
      within(waiting).getByRole("button", { name: "Email my resume to hr@freight.example" }),
    );

    await waitFor(() =>
      expect(findCall(calls, "/applications/a3/send-after-call")?.body).toEqual({
        to: "hr@freight.example",
      }),
    );
  });

  it("saves the daily limit", async () => {
    const calls = mockApi({
      "GET /outbox": () => ({ body: view() }),
      "GET /outbox/contacts": () => ({ body: { rows: [] } }),
      "PUT /outbox/settings": () => ({ body: view({ daily_limit: 10 }) }),
    });
    renderPage(<Outbox />);

    const limit = await screen.findByLabelText("Daily limit");
    await userEvent.clear(limit);
    await userEvent.type(limit, "10");
    await userEvent.click(screen.getByRole("button", { name: "Save limit" }));

    await waitFor(() =>
      expect(findCall(calls, "/outbox/settings")?.body).toEqual({ daily_send_limit: 10 }),
    );
  });

  it("explains an empty outbox", async () => {
    mockApi({
      "GET /outbox": () => ({ body: view({ to_send: [], sending_enabled: true }) }),
      "GET /outbox/contacts": () => ({ body: { rows: [] } }),
    });
    renderPage(<Outbox />);

    expect(await screen.findByText(/Nothing to send yet/)).toBeInTheDocument();
    expect(screen.queryByText(/Email sending is off/)).not.toBeInTheDocument();
  });

  it("a draft follow-up can be sent", async () => {
    const draft: OutboxItem = {
      id: "o1",
      application_id: "a2",
      title: "Analyst",
      company: "Example Health",
      kind: "follow_up",
      application_kind: "advert" as const,
      to: "hr@example.health",
      subject: "Following up on my application",
      scheduled_at: "2026-11-24T20:00:00Z",
      attempts: 0,
      error: null,
    };
    const current = view({ to_send: [], drafts: [draft] });
    const calls = mockApi({
      "GET /outbox": () => ({ body: { ...current, drafts: [draft] } }),
      "GET /outbox/contacts": () => ({ body: { rows: [] } }),
      "POST /outbox/o1/send": () => ({ body: { ...current, drafts: [] } }),
      "POST /outbox/o1/cancel": () => ({ body: { ...current, drafts: [] } }),
    });
    const user = userEvent.setup();
    renderPage(<Outbox />);

    const section = await screen.findByRole("region", { name: "Follow-ups waiting for you" });
    expect(within(section).getByText(/Following up on my application/)).toBeInTheDocument();
    expect(
      within(section).getByText("Send queues this follow-up now. Skip stops follow-ups for this job."),
    ).toBeInTheDocument();
    await user.click(within(section).getByRole("button", { name: "Send" }));
    await waitFor(() => expect(findCall(calls, "/outbox/o1/send")).toBeDefined());
    expect(await screen.findByText(/Nothing to send yet/)).toBeInTheDocument();
  });

  it("skips a draft follow-up", async () => {
    const draft: OutboxItem = {
      id: "o1", application_id: "a2", title: "Analyst", company: "Example Health", kind: "follow_up", application_kind: "advert",
      to: "hr@example.health", subject: "Following up", scheduled_at: "2026-11-24T20:00:00Z",
      attempts: 0, error: null,
    };
    const calls = mockApi({
      "GET /outbox": () => ({ body: view({ to_send: [], drafts: [draft] }) }),
      "GET /outbox/contacts": () => ({ body: { rows: [] } }),
      "POST /outbox/o1/cancel": () => ({ body: view({ to_send: [], drafts: [] }) }),
    });
    const user = userEvent.setup();
    renderPage(<Outbox />);

    const section = await screen.findByRole("region", { name: "Follow-ups waiting for you" });
    await user.click(within(section).getByRole("button", { name: "Skip" }));
    await waitFor(() => expect(findCall(calls, "/outbox/o1/cancel")).toBeDefined());
  });
  it("speculative items are labelled", async () => {
    const speculative = {
      id: "o3",
      application_id: "a3",
      title: "Timber Yard Hand",
      company: "Timaru Trades",
      kind: "application" as const,
      application_kind: "speculative" as const,
      to: "hello@timarutrades.example",
      subject: "Enquiry about opportunities at Timaru Trades",
      scheduled_at: "2026-11-25T08:00:00Z",
      attempts: 0,
      error: null,
    };
    const advert = { ...speculative, id: "o4", application_id: "a4", title: "Driver",
      company: "Example Freight Tech", application_kind: "advert" as const,
      subject: "Application for Driver" };
    mockApi({
      "GET /outbox": () => ({ body: view({ to_send: [], queued: [speculative, advert] }) }),
      "GET /outbox/contacts": () => ({ body: { rows: [] } }),
    });
    renderPage(<Outbox />);

    const queued = await screen.findByRole("region", { name: "Queued" });
    const speculativeItem = within(queued).getByRole("article", { name: /Enquiry about/ });
    expect(within(speculativeItem).getByText("Speculative")).toBeInTheDocument();
    const advertItem = within(queued).getByRole("article", { name: /Application for Driver/ });
    expect(within(advertItem).queryByText("Speculative")).not.toBeInTheDocument();
  });

  it("shows why an advert that asks for applications on the site cannot be queued", async () => {
    mockApi({
      "GET /outbox": () => ({ body: view() }),
      "GET /outbox/contacts": () => ({ body: { rows: [] } }),
      "POST /applications/a1/send": () => ({
        status: 400,
        body: { detail: "This advert asks you to apply on the job site." },
      }),
    });
    renderPage(<Outbox />);

    const item = await screen.findByRole("article", { name: /Data Engineer/ });
    await userEvent.click(within(item).getByRole("button", { name: "Queue email" }));

    expect(
      await screen.findByText("This advert asks you to apply on the job site."),
    ).toBeInTheDocument();
  });

  it("labels a ready-to-apply enquiry as speculative", async () => {
    mockApi({
      "GET /outbox": () => ({
        body: view({
          to_send: [{ ...view().to_send[0], application_kind: "speculative" as const,
            title: "Timber Yard Hand" }],
        }),
      }),
      "GET /outbox/contacts": () => ({ body: { rows: [] } }),
    });
    renderPage(<Outbox />);

    const item = await screen.findByRole("article", { name: /Timber Yard Hand/ });
    expect(within(item).getByText("Speculative")).toBeInTheDocument();
  });
});
