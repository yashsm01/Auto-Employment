import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Phase4View } from "../api/settings";
import { mockApi, renderPage } from "../test/utils";
import Settings from "./Settings";

function view(overrides: Partial<Phase4View> = {}): Phase4View {
  return {
    calls: { configured: true, enabled: true, used_this_month: 1, monthly_limit: 5 },
    whatsapp: { configured: true, to: "+64 22 *** *369" },
    recent_calls: [
      {
        id: "c1",
        purpose: "follow_up",
        status: "done",
        title: "Data Engineer",
        company: "Example Freight Tech",
        created_at: "2026-11-25T22:00:00Z",
        duration_sec: 95,
        captured_email: "hr@freight.example",
        error: null,
        transcript: "Agent: Kia ora\nEmployer: send it to hr@freight.example",
      },
    ],
    ...overrides,
  };
}

const autoMode = {
  enabled: false,
  min_score: 80,
  daily_limit: 5,
  approved_today: 2,
  sending_enabled: false,
  calls_enabled: true,
};

describe("Settings", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows AI calls and WhatsApp status with recent calls", async () => {
    mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: autoMode }),
    });
    renderPage(<Settings />);

    await userEvent.click(await screen.findByRole("tab", { name: "AI calls" }));
    const calls = screen.getByRole("region", { name: "AI phone calls" });
    expect(within(calls).getByText("On")).toBeInTheDocument();
    expect(within(calls).getByText("1 of 5 calls used this month")).toBeInTheDocument();
    const recent = screen.getByRole("region", { name: "Recent calls" });
    expect(within(recent).getByText(/Example Freight Tech/)).toBeInTheDocument();
    expect(within(recent).getByText(/1:35/)).toBeInTheDocument();
    expect(within(recent).getByText("Email given: hr@freight.example")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "WhatsApp" }));
    const whatsapp = screen.getByRole("region", { name: "WhatsApp updates" });
    expect(within(whatsapp).getByText(/\+64 22 \*\*\* \*369/)).toBeInTheDocument();
  });

  it("rings your phone and sends a test WhatsApp", async () => {
    const calls = mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: autoMode }),
      "POST /calls/test": () => ({ body: view() }),
      "POST /notifications/test": () => ({ body: view() }),
    });
    renderPage(<Settings />);

    await userEvent.click(await screen.findByRole("tab", { name: "AI calls" }));
    await userEvent.click(screen.getByRole("button", { name: "Test call to my phone" }));
    await userEvent.click(screen.getByRole("tab", { name: "WhatsApp" }));
    await userEvent.click(screen.getByRole("button", { name: "Send me a test WhatsApp" }));

    await waitFor(() => expect(calls.some((c) => c.path === "/calls/test")).toBe(true));
    await waitFor(() => expect(calls.some((c) => c.path === "/notifications/test")).toBe(true));
    expect(await screen.findByText("Test WhatsApp sent.")).toBeInTheDocument();
  });

  it("explains what to set up when nothing is connected", async () => {
    mockApi({
      "GET /auto-mode": () => ({ body: autoMode }),
      "GET /settings/phase4": () => ({
        body: view({
          calls: { configured: false, enabled: false, used_this_month: 0, monthly_limit: 5 },
          whatsapp: { configured: false, to: null },
          recent_calls: [],
        }),
      }),
    });
    renderPage(<Settings />);

    await userEvent.click(await screen.findByRole("tab", { name: "AI calls" }));
    expect(screen.getByText(/OMNIDIM_AGENT_ID/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "WhatsApp" }));
    expect(screen.getByText(/WHATSAPP_TO/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Test call to my phone" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Send me a test WhatsApp" })).not.toBeInTheDocument();
  });

  it("switches auto mode on with its limits", async () => {
    const calls = mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: autoMode }),
      "PUT /auto-mode": (body) => ({ body: { ...autoMode, ...(body as object) } }),
    });
    renderPage(<Settings />);

    const card = await screen.findByRole("region", { name: "Auto mode" });
    expect(within(card).getByText("2 jobs approved by auto mode today")).toBeInTheDocument();
    expect(within(card).getByText(/Email sending is off/)).toBeInTheDocument();
    await userEvent.click(within(card).getByRole("checkbox", { name: "Auto mode" }));
    const score = within(card).getByLabelText("Minimum score");
    await userEvent.clear(score);
    await userEvent.type(score, "85");
    const limit = within(card).getByLabelText("Jobs a day");
    await userEvent.clear(limit);
    await userEvent.type(limit, "3");
    await userEvent.click(within(card).getByRole("button", { name: "Save auto mode" }));

    expect(await within(card).findByText("Auto mode settings saved.")).toBeInTheDocument();
    await waitFor(() =>
      expect(calls.find((c) => c.method === "PUT" && c.path === "/auto-mode")?.body).toEqual({
        enabled: true,
        min_score: 85,
        daily_limit: 3,
      }),
    );
  });

  it("shows a QR code to link WhatsApp, then lets you unlink it", async () => {
    type Link = { state: string; qr: string | null; me: string | null; error: string | null };
    let link: Link = { state: "qr", qr: "data:image/png;base64,AAAA", me: null, error: null };
    const calls = mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: autoMode }),
      "GET /whatsapp/status": () => ({ body: link }),
      "POST /whatsapp/logout": () => ({ body: { state: "logged_out" } }),
    });
    renderPage(<Settings />);

    await userEvent.click(await screen.findByRole("tab", { name: "WhatsApp" }));
    const panel = screen.getByRole("region", { name: "WhatsApp link" });
    expect(await within(panel).findByRole("img", { name: "WhatsApp QR code" })).toHaveAttribute(
      "src",
      "data:image/png;base64,AAAA",
    );
    expect(within(panel).getByText(/Linked devices/)).toBeInTheDocument();

    link = { state: "connected", qr: null, me: "+64 22 *** *369", error: null };
    expect(await within(panel).findByText("Linked to +64 22 *** *369", {}, { timeout: 5000 }))
      .toBeInTheDocument();
    await userEvent.click(within(panel).getByRole("button", { name: "Unlink WhatsApp" }));
    await waitFor(() => expect(calls.some((c) => c.path === "/whatsapp/logout")).toBe(true));
  });

  it("explains how to start the WhatsApp service when it isn't running", async () => {
    mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: autoMode }),
      "GET /whatsapp/status": () => ({
        body: { state: "offline", qr: null, me: null, error: "did not answer" },
      }),
    });
    renderPage(<Settings />);

    await userEvent.click(await screen.findByRole("tab", { name: "WhatsApp" }));

    expect(await screen.findByText(/npm start/)).toBeInTheDocument();
  });
});
