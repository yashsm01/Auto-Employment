import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

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

function withApi(initial: SavedEmployer[] = []) {
  let list = initial;
  return mockApi({
    "GET /employers": () => ({ body: { items: list } }),
    "POST /employers/search": () => ({ body: { results: [nearby()], searches_left: 29 } }),
    "POST /employers": () => {
      list = [saved()];
      return { body: saved() };
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
});
