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
  prospects_enabled: false,
  prospects_per_day: 5,
  business_types: [] as string[],
  business_types_suggested: [] as string[],
  approved_today: 2,
  sending_enabled: false,
  calls_enabled: true,
};

const googleMaps = {
  ...autoMode,
  enabled: true,
  prospects_enabled: true,
  prospects_per_day: 4,
  business_types: ["Plumbing", "Electrical"],
};

const GOOGLE_SWITCH = "Email Google Maps employers automatically";

describe("Settings", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows AI calls and WhatsApp status with recent calls", async () => {
    mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: autoMode }),
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
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
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
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
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
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
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
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
        prospects_enabled: false,
        prospects_per_day: 5,
        business_types: [],
      }),
    );
  });

  it("saving the existing auto mode fields keeps the Google Maps settings", async () => {
    const calls = mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: googleMaps }),
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
      "PUT /auto-mode": (body) => ({ body: { ...googleMaps, ...(body as object) } }),
    });
    renderPage(<Settings />);

    const card = await screen.findByRole("region", { name: "Auto mode" });
    const score = within(card).getByLabelText("Minimum score");
    await userEvent.clear(score);
    await userEvent.type(score, "90");
    await userEvent.click(within(card).getByRole("button", { name: "Save auto mode" }));

    expect(await within(card).findByText("Auto mode settings saved.")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PUT" && c.path === "/auto-mode")?.body).toEqual({
      enabled: true,
      min_score: 90,
      daily_limit: 5,
      prospects_enabled: true,
      prospects_per_day: 4,
      business_types: ["Plumbing", "Electrical"],
    });
  });

  it("the Google Maps settings save", async () => {
    const calls = mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: { ...googleMaps, prospects_enabled: false } }),
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
      "PUT /auto-mode": (body) => ({ body: { ...googleMaps, ...(body as object) } }),
    });
    renderPage(<Settings />);

    const card = await screen.findByRole("region", { name: "Auto mode" });
    await userEvent.click(within(card).getByRole("checkbox", { name: GOOGLE_SWITCH }));
    const perDay = within(card).getByLabelText("New employers a day");
    await userEvent.clear(perDay);
    await userEvent.type(perDay, "7");
    await userEvent.type(within(card).getByLabelText("Add a business type"), "Roofing{Enter}");
    await userEvent.click(within(card).getByRole("button", { name: "Save auto mode" }));

    expect(await within(card).findByText("Auto mode settings saved.")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PUT" && c.path === "/auto-mode")?.body).toEqual({
      enabled: true,
      min_score: 80,
      daily_limit: 5,
      prospects_enabled: true,
      prospects_per_day: 7,
      business_types: ["Plumbing", "Electrical", "Roofing"],
    });
  });

  it("the switch reads off while Auto mode is off, even when outreach is stored on", async () => {
    mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: { ...googleMaps, enabled: false } }),
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
    });
    renderPage(<Settings />);

    const card = await screen.findByRole("region", { name: "Auto mode" });
    const googleSwitch = within(card).getByRole("checkbox", { name: GOOGLE_SWITCH });
    expect(googleSwitch).not.toBeChecked();
    expect(googleSwitch).toBeDisabled();
    expect(within(card).getByText("Turn on Auto mode first.")).toBeInTheDocument();
  });

  it("the switch needs Auto mode", async () => {
    const calls = mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: { ...googleMaps, enabled: false } }),
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
      "PUT /auto-mode": (body) => ({ body }),
    });
    renderPage(<Settings />);

    const card = await screen.findByRole("region", { name: "Auto mode" });
    expect(within(card).getByRole("checkbox", { name: GOOGLE_SWITCH })).toBeDisabled();
    expect(within(card).getByText("Turn on Auto mode first.")).toBeInTheDocument();

    await userEvent.click(within(card).getByRole("checkbox", { name: "Auto mode" }));
    expect(within(card).getByRole("checkbox", { name: GOOGLE_SWITCH })).toBeEnabled();
    expect(within(card).queryByText("Turn on Auto mode first.")).not.toBeInTheDocument();

    // Turning Auto mode back off must not send Google Maps outreach on, which the server refuses.
    await userEvent.click(within(card).getByRole("checkbox", { name: "Auto mode" }));
    await userEvent.click(within(card).getByRole("button", { name: "Save auto mode" }));
    await waitFor(() =>
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual(
        expect.objectContaining({ enabled: false, prospects_enabled: false }),
      ),
    );
  });

  it("shows the server's refusal when Google Maps outreach needs Auto mode", async () => {
    mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: autoMode }),
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
      "PUT /auto-mode": () => ({ status: 400, body: { detail: "Turn on Auto mode first." } }),
    });
    renderPage(<Settings />);

    const card = await screen.findByRole("region", { name: "Auto mode" });
    await userEvent.click(within(card).getByRole("checkbox", { name: "Auto mode" }));
    await userEvent.click(within(card).getByRole("button", { name: "Save auto mode" }));

    expect(await within(card).findByRole("alert")).toHaveTextContent("Turn on Auto mode first.");
  });

  it("business types start from the suggestions until you save", async () => {
    const calls = mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({
        body: { ...autoMode, enabled: true, business_types_suggested: ["Cafe", "Plumbing"] },
      }),
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
      "PUT /auto-mode": (body) => ({ body }),
    });
    renderPage(<Settings />);

    const card = await screen.findByRole("region", { name: "Auto mode" });
    expect(within(card).getByText(/Suggested from your resume/)).toBeInTheDocument();
    await userEvent.click(within(card).getByRole("button", { name: "Remove Cafe" }));
    await userEvent.click(within(card).getByRole("button", { name: "Save auto mode" }));

    await waitFor(() =>
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual(
        expect.objectContaining({ business_types: ["Plumbing"] }),
      ),
    );
  });

  it("refuses a business type that is too long and ignores a duplicate", async () => {
    mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: { ...autoMode, business_types: ["Plumbing"] } }),
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
    });
    renderPage(<Settings />);

    const card = await screen.findByRole("region", { name: "Auto mode" });
    await userEvent.type(within(card).getByLabelText("Add a business type"), "plumbing{Enter}");
    expect(within(card).getAllByRole("button", { name: /^Remove / })).toHaveLength(1);
    await userEvent.type(within(card).getByLabelText("Add a business type"), `${"x".repeat(61)}{Enter}`);
    expect(within(card).getByText("Business types can be up to 60 characters.")).toBeInTheDocument();
  });

  it("shows a QR code to link WhatsApp, then lets you unlink it", async () => {
    type Link = { state: string; qr: string | null; me: string | null; error: string | null };
    let link: Link = { state: "qr", qr: "data:image/png;base64,AAAA", me: null, error: null };
    const calls = mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: autoMode }),
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
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
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
      "GET /whatsapp/status": () => ({
        body: { state: "offline", qr: null, me: null, error: "did not answer" },
      }),
    });
    renderPage(<Settings />);

    await userEvent.click(await screen.findByRole("tab", { name: "WhatsApp" }));

    expect(await screen.findByText(/npm start/)).toBeInTheDocument();
  });

  it("the follow-up switch saves ask", async () => {
    const calls = mockApi({
      "GET /settings/phase4": () => ({ body: view() }),
      "GET /auto-mode": () => ({ body: autoMode }),
      "GET /settings/follow-ups": () => ({ body: { mode: "auto" } }),
      "PUT /settings/follow-ups": (body) => ({ body }),
    });
    renderPage(<Settings />);

    const auto = await screen.findByRole("radio", { name: "Send follow-ups automatically" });
    expect(auto).toBeChecked();
    await userEvent.click(screen.getByRole("radio", { name: "Ask me before each follow-up" }));

    expect(await screen.findByText("Follow-up setting saved.")).toBeInTheDocument();
    expect(calls).toContainEqual({
      method: "PUT",
      path: "/settings/follow-ups",
      body: { mode: "ask" },
    });
  });
});
