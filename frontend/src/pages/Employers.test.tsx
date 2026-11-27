import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { NearbyEmployer, SavedEmployer } from "../api/employers";
import { mockApi, renderPage } from "../test/utils";
import Employers from "./Employers";

function nearby(overrides: Partial<NearbyEmployer> = {}): NearbyEmployer {
  return {
    place_id: "place-1",
    name: "Acme Software",
    address: "1 Stafford St, Timaru 7910, New Zealand",
    phone: "03 000 0000",
    website: "https://acme.co.nz/",
    lat: -44.39,
    lng: 171.25,
    map_url: "https://www.google.com/maps/search/?api=1&query=1%20Stafford%20St",
    saved: false,
    rating: 4.6,
    rating_count: 120,
    hours: ["Monday: 9:00 AM – 5:00 PM"],
    business_type: "Software company",
    ...overrides,
  };
}

function saved(overrides: Partial<SavedEmployer> = {}): SavedEmployer {
  return {
    id: "c1",
    name: "Acme Software",
    address: "1 Stafford St, Timaru 7910, New Zealand",
    phone: "03 000 0000",
    website: "https://acme.co.nz/",
    map_url: "https://www.google.com/maps/search/?api=1&query=Acme",
    last_checked: null,
    ...overrides,
  };
}

const lookedUp = {
  phone: "03 000 0000",
  phone_source: "Google Maps",
  emails: ["info@acme.co.nz"],
  hiring_emails: [],
  hours: [],
  recruiters: [],
  notes: ["Could not read the careers page (timed out)."],
  checked_at: "2026-11-26T01:00:00Z",
};

function withApi(initial: SavedEmployer[] = []) {
  let list = initial;
  return mockApi({
    "GET /employers": () => ({ body: { items: list } }),
    "POST /employers/search": () => ({ body: { results: [nearby()], searches_left: 29 } }),
    "POST /employers": () => {
      list = [saved()];
      return { body: saved() };
    },
    "POST /employers/c1/contacts": () => {
      // The saved list then carries the stored contacts, which do not include this run's notes.
      list = [saved({ contacts: { ...lookedUp, notes: [] } })];
      return { body: lookedUp };
    },
    "DELETE /employers/c1": () => {
      list = [];
      return { body: { removed: true } };
    },
  });
}

async function search(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Type of business"), "software company");
  await user.type(screen.getByLabelText("Town or region"), "Timaru");
  await user.click(screen.getByRole("button", { name: "Search Google Maps" }));
}

describe("Employers", () => {
  it("searches Google Maps and shows where each result came from", async () => {
    const calls = withApi();
    const user = userEvent.setup();
    renderPage(<Employers />);
    await screen.findByRole("heading", { name: "Nearby employers", level: 1 });

    await search(user);

    const card = (await screen.findByRole("heading", { name: "Acme Software" })).closest("article")!;
    expect(within(card).getByText("Google Maps")).toBeInTheDocument();
    expect(within(card).getByText(/1 Stafford St, Timaru/)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: /map/i })).toHaveAttribute(
      "href",
      expect.stringContaining("google.com/maps"),
    );
    expect(within(card).getByRole("link", { name: /website/i })).toHaveAttribute(
      "href",
      "https://acme.co.nz/",
    );
    expect(screen.getByText(/29 searches left today/)).toBeInTheDocument();
    expect(calls).toContainEqual({
      method: "POST",
      path: "/employers/search",
      body: { business: "software company", town: "Timaru" },
    });
  });

  it("saves an employer so searches check its website", async () => {
    const calls = withApi();
    const user = userEvent.setup();
    renderPage(<Employers />);
    await screen.findByRole("heading", { name: "Nearby employers", level: 1 });
    await search(user);

    await user.click(await screen.findByRole("button", { name: "Save Acme Software" }));

    expect(await screen.findByRole("button", { name: "Saved" })).toBeDisabled();
    const save = calls.find((call) => call.method === "POST" && call.path === "/employers")!;
    expect(save.body).toEqual({
      place_id: "place-1",
      name: "Acme Software",
      address: "1 Stafford St, Timaru 7910, New Zealand",
      phone: "03 000 0000",
      website: "https://acme.co.nz/",
      lat: -44.39,
      lng: 171.25,
      rating: 4.6,
      rating_count: 120,
      hours: ["Monday: 9:00 AM – 5:00 PM"],
    });
    const list = screen.getByRole("region", { name: "Employers checked on each search" });
    expect(await within(list).findByText("Acme Software")).toBeInTheDocument();
  });

  it("shows an employer already saved as saved", async () => {
    mockApi({
      "GET /employers": () => ({ body: { items: [] } }),
      "POST /employers/search": () => ({
        body: { results: [nearby({ saved: true })], searches_left: 3 },
      }),
    });
    const user = userEvent.setup();
    renderPage(<Employers />);
    await screen.findByRole("heading", { name: "Nearby employers", level: 1 });

    await search(user);

    expect(await screen.findByRole("button", { name: "Saved" })).toBeDisabled();
  });

  it("lists saved employers with when their website was last checked", async () => {
    withApi([saved({ last_checked: "2026-11-24T07:00:00Z" })]);
    renderPage(<Employers />);

    const list = await screen.findByRole("region", { name: "Employers checked on each search" });

    expect(await within(list).findByText("Acme Software")).toBeInTheDocument();
    expect(within(list).getByText(/Website checked/)).toBeInTheDocument();
  });

  it("removes a saved employer", async () => {
    const calls = withApi([saved()]);
    const user = userEvent.setup();
    renderPage(<Employers />);

    await user.click(await screen.findByRole("button", { name: "Remove Acme Software" }));

    expect(await screen.findByText(/No employers saved yet/)).toBeInTheDocument();
    expect(calls.some((call) => call.method === "DELETE" && call.path === "/employers/c1")).toBe(
      true,
    );
  });

  it("shows rating, business type and opening hours for search results", async () => {
    withApi();
    const user = userEvent.setup();
    renderPage(<Employers />);
    await screen.findByRole("heading", { name: "Nearby employers", level: 1 });

    await search(user);

    const card = (await screen.findByRole("heading", { name: "Acme Software" })).closest("article")!;
    expect(within(card).getByText("★ 4.6 (120)")).toBeInTheDocument();
    expect(within(card).getByText("Software company")).toBeInTheDocument();
    const hours = within(card).getByText("Opening hours").closest("details")!;
    expect(within(hours).getByText("Monday: 9:00 AM – 5:00 PM")).toBeInTheDocument();
  });

  it("gets contact details for a saved employer and shows the result with its notes", async () => {
    const calls = withApi([saved()]);
    const user = userEvent.setup();
    renderPage(<Employers />);
    const list = await screen.findByRole("region", { name: "Employers checked on each search" });

    await user.click(await within(list).findByRole("button", { name: "Get contact details" }));

    expect(calls).toContainEqual({
      method: "POST",
      path: "/employers/c1/contacts",
      body: undefined,
    });
    expect(await within(list).findByText("info@acme.co.nz")).toBeInTheDocument();
    expect(within(list).getByText("Could not read the careers page (timed out).")).toBeInTheDocument();
  });

  it("shows a contact lookup problem in the page notice", async () => {
    mockApi({
      "GET /employers": () => ({ body: { items: [saved()] } }),
      "POST /employers/c1/contacts": () => ({
        status: 500,
        body: { detail: "The contact lookup failed." },
      }),
    });
    const user = userEvent.setup();
    renderPage(<Employers />);
    const list = await screen.findByRole("region", { name: "Employers checked on each search" });

    await user.click(await within(list).findByRole("button", { name: "Get contact details" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The contact lookup failed.");
  });

  it("keeps each card's busy state and notes when two lookups overlap", async () => {
    const release: Record<string, () => void> = {};
    const gated = (id: string) => new Promise<void>((resolve) => (release[id] = resolve));
    const waits: Record<string, Promise<void>> = { c1: gated("c1"), c2: gated("c2") };
    mockApi({
      "GET /employers": () => ({
        body: { items: [saved(), saved({ id: "c2", name: "Beta Builders" })] },
      }),
      "POST /employers/c1/contacts": () => ({ body: { ...lookedUp, notes: ["Note for Acme."] } }),
      "POST /employers/c2/contacts": () => ({ body: { ...lookedUp, notes: ["Note for Beta."] } }),
    });
    const answer = globalThis.fetch;
    vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
      const id = new URL(url).pathname.split("/")[2];
      if (init?.method === "POST" && id in waits) await waits[id];
      return answer(url, init);
    });
    const user = userEvent.setup();
    renderPage(<Employers />);
    const list = await screen.findByRole("region", { name: "Employers checked on each search" });
    const acme = (await within(list).findByText("Acme Software")).parentElement!.parentElement!;
    const beta = (await within(list).findByText("Beta Builders")).parentElement!.parentElement!;

    await user.click(within(acme).getByRole("button", { name: "Get contact details" }));
    await user.click(within(beta).getByRole("button", { name: "Get contact details" }));

    expect(within(acme).getByRole("button", { name: "Get contact details" })).toBeDisabled();
    expect(within(beta).getByRole("button", { name: "Get contact details" })).toBeDisabled();

    release.c2();
    expect(await within(beta).findByText("Note for Beta.")).toBeInTheDocument();
    expect(within(beta).getByRole("button", { name: "Get contact details" })).toBeEnabled();
    expect(within(acme).getByRole("button", { name: "Get contact details" })).toBeDisabled();

    release.c1();
    expect(await within(acme).findByText("Note for Acme.")).toBeInTheDocument();
    expect(within(acme).getByRole("button", { name: "Get contact details" })).toBeEnabled();
  });

  it("does not link a search result website that is not http", async () => {
    mockApi({
      "GET /employers": () => ({ body: { items: [] } }),
      "POST /employers/search": () => ({
        body: { results: [nearby({ website: "javascript:alert(1)" })], searches_left: 3 },
      }),
    });
    const user = userEvent.setup();
    renderPage(<Employers />);
    await screen.findByRole("heading", { name: "Nearby employers", level: 1 });

    await search(user);

    const card = (await screen.findByRole("heading", { name: "Acme Software" })).closest("article")!;
    expect(within(card).queryByRole("link", { name: "Website" })).toBeNull();
  });

  it("does not link a map that is not http, in search results or saved employers", async () => {
    mockApi({
      "GET /employers": () => ({ body: { items: [saved({ map_url: "javascript:alert(1)" })] } }),
      "POST /employers/search": () => ({
        body: { results: [nearby({ map_url: "javascript:alert(1)" })], searches_left: 3 },
      }),
    });
    const user = userEvent.setup();
    renderPage(<Employers />);
    const list = await screen.findByRole("region", { name: "Employers checked on each search" });
    expect(await within(list).findByText("Acme Software")).toBeInTheDocument();
    expect(within(list).queryByRole("link", { name: "Map" })).toBeNull();

    await screen.findByRole("heading", { name: "Nearby employers", level: 1 });
    await search(user);

    const card = (await screen.findByRole("heading", { name: "Acme Software", level: 3 })).closest("article")!;
    expect(within(card).queryByRole("link", { name: /open map/i })).toBeNull();
  });

  it("explains a search problem such as a missing key", async () => {
    mockApi({
      "GET /employers": () => ({ body: { items: [] } }),
      "POST /employers/search": () => ({
        status: 400,
        body: { detail: "Google Maps is not connected. Add GOOGLE_MAPS_API_KEY to backend/.env" },
      }),
    });
    const user = userEvent.setup();
    renderPage(<Employers />);
    await screen.findByRole("heading", { name: "Nearby employers", level: 1 });

    await search(user);

    expect(await screen.findByRole("alert")).toHaveTextContent("GOOGLE_MAPS_API_KEY");
  });

  it("saved employers show outreach status", async () => {
    withApi([
      saved({ id: "c1", name: "Emailed Ltd", outreach_status: "emailed", outreach_at: "2026-11-25T22:00:00Z" }),
      saved({ id: "c2", name: "Replied Ltd", outreach_status: "replied", outreach_at: "2026-11-20T03:00:00Z" }),
      saved({ id: "c3", name: "Blocked Ltd", outreach_status: "blocked", outreach_at: null }),
      saved({ id: "c4", name: "Quiet Ltd", outreach_status: null, outreach_at: null }),
    ]);
    renderPage(<Employers />);

    const list = await screen.findByRole("region", { name: "Employers checked on each search" });
    // 25 November 22:00 UTC is 26 November in New Zealand.
    expect(await within(list).findByText("Emailed 26 Nov 2026")).toBeInTheDocument();
    expect(within(list).getByText("Replied")).toBeInTheDocument();
    expect(within(list).getByText("Do not contact")).toBeInTheDocument();
    const quiet = within(list).getByText("Quiet Ltd").closest("div")!.parentElement!;
    expect(within(quiet).queryByText(/Emailed|Replied|Do not contact/)).not.toBeInTheDocument();
  });
});
