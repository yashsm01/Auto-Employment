import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ContactRow } from "../api/outbox";
import { mockApi, renderPage } from "../test/utils";
import OutboxContacts from "./OutboxContacts";

function row(overrides: Partial<ContactRow> = {}): ContactRow {
  return {
    application_id: "a1",
    title: "Data Engineer",
    company: "Acme Ltd",
    kind: "advert",
    status: "approved",
    hiring_emails: ["hiring@acme.example"],
    emails: ["info@acme.example"],
    advert_contact: {
      name: "Jane Example",
      role: "Recruiter",
      email: "jane@acme.example",
      phone: "03 000 2222",
    },
    phone: "03 000 1111",
    phone_source: "Google Maps",
    address_used: "hiring@acme.example",
    missing_reason: null,
    checked_at: "2026-11-26T01:00:00Z",
    ...overrides,
  };
}

const missing = row({
  application_id: "a2",
  title: "Analyst",
  company: "Example Health",
  hiring_emails: [],
  emails: [],
  advert_contact: null,
  phone: null,
  phone_source: null,
  address_used: null,
  missing_reason: "No email address was found in the advert or on their website.",
  checked_at: null,
});

describe("OutboxContacts", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("contacts list shows details and reasons", async () => {
    mockApi({ "GET /outbox/contacts": () => ({ body: { rows: [row(), missing] } }) });
    renderPage(<OutboxContacts />);

    const list = await screen.findByRole("region", { name: "Contacts" });
    const first = within(list).getByRole("article", { name: "Data Engineer at Acme Ltd" });
    expect(within(first).getByText("hiring@acme.example")).toBeInTheDocument();
    expect(within(first).getByText("info@acme.example")).toBeInTheDocument();
    expect(within(first).getByText("From the advert")).toBeInTheDocument();
    expect(within(first).getByText("Jane Example")).toBeInTheDocument();
    expect(within(first).getByText("Recruiter")).toBeInTheDocument();
    expect(within(first).getByText("jane@acme.example")).toBeInTheDocument();
    expect(within(first).getByText("03 000 2222")).toBeInTheDocument();
    expect(within(first).getByText("03 000 1111")).toBeInTheDocument();
    expect(within(first).getByText("From Google Maps")).toBeInTheDocument();
    expect(within(first).getByText("Address used: hiring@acme.example")).toBeInTheDocument();
    expect(within(first).queryByText("Speculative")).not.toBeInTheDocument();
    // The response does not say where the email lists came from, so no source label is shown for them.
    expect(within(list).queryByText("From their website")).not.toBeInTheDocument();

    const second = within(list).getByRole("article", { name: "Analyst at Example Health" });
    expect(
      within(second).getByText("No email address was found in the advert or on their website."),
    ).toBeInTheDocument();
    expect(within(second).queryByText("Address used:", { exact: false })).not.toBeInTheDocument();
  });

  it("Find contacts posts and updates the row", async () => {
    const found = row({
      application_id: "a2",
      title: "Analyst",
      company: "Example Health",
      hiring_emails: [],
      emails: ["careers@health.example"],
      phone: null,
      phone_source: null,
      address_used: "careers@health.example",
      missing_reason: null,
      checked_at: "2026-11-26T01:00:00Z",
    });
    const calls = mockApi({
      "GET /outbox/contacts": () => ({ body: { rows: [missing] } }),
      "POST /applications/a2/find-contacts": () => ({ body: found }),
    });
    const user = userEvent.setup();
    renderPage(<OutboxContacts />);

    const list = await screen.findByRole("region", { name: "Contacts" });
    await user.click(within(list).getByRole("button", { name: "Find contacts for Example Health" }));

    expect(await within(list).findByText("careers@health.example")).toBeInTheDocument();
    expect(within(list).queryByText(/No email address was found/)).not.toBeInTheDocument();
    expect(calls).toContainEqual({
      method: "POST",
      path: "/applications/a2/find-contacts",
      body: undefined,
    });
  });

  it("shows the error when finding contacts fails", async () => {
    mockApi({
      "GET /outbox/contacts": () => ({ body: { rows: [missing] } }),
      "POST /applications/a2/find-contacts": () => ({
        status: 500,
        body: { detail: "The website could not be reached." },
      }),
    });
    const user = userEvent.setup();
    renderPage(<OutboxContacts />);

    const list = await screen.findByRole("region", { name: "Contacts" });
    await user.click(within(list).getByRole("button", { name: "Find contacts for Example Health" }));

    expect(await within(list).findByRole("alert")).toHaveTextContent(
      "The website could not be reached.",
    );
  });
});
