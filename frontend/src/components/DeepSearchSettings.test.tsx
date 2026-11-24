import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockApi, renderPage } from "../test/utils";
import DeepSearchSettings from "./DeepSearchSettings";

const settings = { enabled: false, monthly_limit: 30, used_this_month: 3, available: true };

describe("DeepSearchSettings", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("saves the switch and the monthly limit", async () => {
    const calls = mockApi({
      "GET /deep-search": () => ({ body: settings }),
      "PUT /deep-search": (body) => ({ body: { ...settings, ...(body as object) } }),
    });
    renderPage(<DeepSearchSettings />);

    const toggle = await screen.findByRole("checkbox", { name: "Deep search" });
    expect(toggle).not.toBeChecked();
    expect(screen.getByText("3 of 30 deep searches used this month")).toBeInTheDocument();
    await userEvent.click(toggle);
    const limit = screen.getByLabelText("Monthly limit");
    await userEvent.clear(limit);
    await userEvent.type(limit, "20");
    await userEvent.click(screen.getByRole("button", { name: "Save deep search settings" }));

    expect(await screen.findByText("Deep search settings saved.")).toBeInTheDocument();
    await waitFor(() =>
      expect(calls.find((c) => c.method === "PUT")?.body).toEqual({
        enabled: true,
        monthly_limit: 20,
      }),
    );
  });

  it("says when a Claude key is needed", async () => {
    mockApi({ "GET /deep-search": () => ({ body: { ...settings, available: false } }) });
    renderPage(<DeepSearchSettings />);

    expect(
      await screen.findByText("Deep search needs a Claude key in backend/.env."),
    ).toBeInTheDocument();
  });
});
