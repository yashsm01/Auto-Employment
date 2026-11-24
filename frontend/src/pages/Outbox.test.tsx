import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { OutboxView } from "../api/outbox";
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

  it("saves the daily limit", async () => {
    const calls = mockApi({
      "GET /outbox": () => ({ body: view() }),
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
    mockApi({ "GET /outbox": () => ({ body: view({ to_send: [], sending_enabled: true }) }) });
    renderPage(<Outbox />);

    expect(await screen.findByText(/Nothing to send yet/)).toBeInTheDocument();
    expect(screen.queryByText(/Email sending is off/)).not.toBeInTheDocument();
  });
});
