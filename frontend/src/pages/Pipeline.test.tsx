import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Pipeline as PipelineData } from "../api/pipeline";
import { mockApi, renderPage } from "../test/utils";
import Pipeline from "./Pipeline";

function pipeline(isExample = false, shortlisted = 1): PipelineData {
  const cards = Array.from({ length: shortlisted }, (_, index) => ({
    id: `a${index}`,
    title: `Python Developer ${index + 1}`,
    company: "Freight Tech",
    city: "Auckland",
    score: 87,
    meta: "Matched: Python",
    is_example: isExample,
  }));
  return {
    stats: { found_today: 34, shortlisted, ready_to_send: 2, replies_this_week: 1 },
    last_run_at: "2026-11-24T07:00:00Z",
    columns: [
      { key: "shortlisted", name: "Shortlisted", count: shortlisted, cards },
      { key: "resume_ready", name: "Resume ready", count: 0, cards: [] },
      { key: "sent", name: "Sent", count: 0, cards: [] },
      { key: "followed_up", name: "Followed up", count: 0, cards: [] },
      { key: "replied", name: "Replied", count: 0, cards: [] },
    ],
  };
}

const runReply = (output: Record<string, unknown>, status = "ok", error: string | null = null) => ({
  body: { id: "r1", status, output, error },
});

describe("Pipeline", () => {
  it("shows the stats", async () => {
    mockApi({ "GET /pipeline": () => ({ body: pipeline() }) });
    renderPage(<Pipeline />);

    const stat = (await screen.findByText("Found today")).parentElement!;

    expect(within(stat).getByText("34")).toBeInTheDocument();
  });

  it("puts each card in its column", async () => {
    mockApi({ "GET /pipeline": () => ({ body: pipeline() }) });
    renderPage(<Pipeline />);

    const column = await screen.findByRole("region", { name: "Shortlisted" });

    expect(within(column).getByText("Python Developer 1")).toBeInTheDocument();
    expect(within(column).getByText("Freight Tech · Auckland")).toBeInTheDocument();
    expect(
      within(screen.getByRole("region", { name: "Sent" })).queryByText("Python Developer 1"),
    ).toBeNull();
  });

  it("runs a search and refreshes the board", async () => {
    let current = pipeline(false, 1);
    const calls = mockApi({
      "GET /pipeline": () => ({ body: current }),
      "POST /runs/lead": () => {
        current = pipeline(false, 2);
        return runReply({ new_jobs: 5, shortlisted: 1, errors: [] });
      },
    });
    const user = userEvent.setup();
    renderPage(<Pipeline />);
    await screen.findByText("Python Developer 1");

    await user.click(screen.getByRole("button", { name: "Run search now" }));

    expect(await screen.findByRole("status")).toHaveTextContent("5 new jobs, 1 shortlisted");
    expect(await screen.findByText("Python Developer 2")).toBeInTheDocument();
    expect(calls.filter((call) => call.method === "POST")).toHaveLength(1);
  });

  it("warns when a source failed but the run finished", async () => {
    mockApi({
      "GET /pipeline": () => ({ body: pipeline() }),
      "POST /runs/lead": () => runReply({ new_jobs: 0, shortlisted: 0, errors: ["trademe: HTTP 401"] }),
    });
    const user = userEvent.setup();
    renderPage(<Pipeline />);
    await screen.findByText("Python Developer 1");

    await user.click(screen.getByRole("button", { name: "Run search now" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("trademe: HTTP 401");
  });

  it("shows the error when a run fails", async () => {
    mockApi({
      "GET /pipeline": () => ({ body: pipeline() }),
      "POST /runs/lead": () => runReply({}, "error", "RuntimeError: model unavailable"),
    });
    const user = userEvent.setup();
    renderPage(<Pipeline />);
    await screen.findByText("Python Developer 1");

    await user.click(screen.getByRole("button", { name: "Run search now" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("model unavailable");
    expect(screen.queryByRole("status")).not.toBeInTheDocument();
  });

  it("tells the user when a search is already running", async () => {
    mockApi({
      "GET /pipeline": () => ({ body: pipeline() }),
      "POST /runs/lead": () => ({
        status: 409,
        body: { detail: "The lead search is already running" },
      }),
    });
    const user = userEvent.setup();
    renderPage(<Pipeline />);
    await screen.findByText("Python Developer 1");

    await user.click(screen.getByRole("button", { name: "Run search now" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("already running");
  });

  it("labels example data", async () => {
    mockApi({ "GET /pipeline": () => ({ body: pipeline(true) }) });
    renderPage(<Pipeline />);

    expect(await screen.findByText("Example data")).toBeInTheDocument();
  });

  it("does not label real data as an example", async () => {
    mockApi({ "GET /pipeline": () => ({ body: pipeline(false) }) });
    renderPage(<Pipeline />);
    await screen.findByText("Python Developer 1");

    expect(screen.queryByText("Example data")).not.toBeInTheDocument();
  });

  it("shows a load failure", async () => {
    mockApi({ "GET /pipeline": () => ({ status: 500, body: { detail: "Database down" } }) });
    renderPage(<Pipeline />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Database down");
  });
});
