import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { Coverage, SkillCoverage } from "../api/resumes";
import CoveragePanel from "./CoveragePanel";

function skill(overrides: Partial<SkillCoverage> = {}): SkillCoverage {
  return { name: "Python", status: "shown", evidence: "Built data pipelines.", matched_as: null, ...overrides };
}

function coverage(overrides: Partial<Coverage> = {}): Coverage {
  return {
    required: [skill({ name: "SQL" })],
    preferred: [skill({ name: "dbt", status: "missing", evidence: "" })],
    split: true,
    required_text: "1 of 1",
    preferred_text: "0 of 1",
    ...overrides,
  };
}

describe("CoveragePanel", () => {
  it("groups and counts follow split", () => {
    const { unmount } = render(<CoveragePanel coverage={coverage()} onDecide={vi.fn()} />);

    const required = screen.getByRole("group", { name: /Required in the ad/ });
    expect(within(required).getByText("SQL")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /Nice to have/ })).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /Skills the ad mentions/ })).toBeNull();
    expect(screen.getByText("Skill coverage for this job")).toBeInTheDocument();
    expect(
      screen.getByText(
        "How many of the ad's skills your CV shows, and where. Employers' systems differ, so this is a guide, not a prediction of an interview.",
      ),
    ).toBeInTheDocument();
    unmount();

    render(
      <CoveragePanel
        coverage={coverage({ split: false, required: [], preferred: [skill({ name: "dbt", status: "missing", evidence: "" }), skill({ name: "SQL" })] })}
        onDecide={vi.fn()}
      />,
    );
    const mentioned = screen.getByRole("group", { name: /Skills the ad mentions/ });
    expect(within(mentioned).getByText("dbt")).toBeInTheDocument();
    expect(within(mentioned).getByText("SQL")).toBeInTheDocument();
    expect(screen.queryByRole("group", { name: /Required in the ad/ })).toBeNull();
  });

  it("the empty message shows with no skills", () => {
    render(
      <CoveragePanel
        coverage={coverage({ required: [], preferred: [], split: false, required_text: "0 of 0", preferred_text: "0 of 0" })}
        onDecide={vi.fn()}
      />,
    );

    expect(screen.getByText("No skills found in this ad.")).toBeInTheDocument();
  });

  it("I have this posts have and Undo posts null", async () => {
    const onDecide = vi.fn();
    const user = userEvent.setup();
    const { rerender } = render(
      <CoveragePanel coverage={coverage()} onDecide={onDecide} />,
    );

    await user.click(screen.getByRole("button", { name: "I have this: dbt" }));
    expect(onDecide).toHaveBeenCalledWith("dbt", "have");

    await user.click(screen.getByRole("button", { name: "Not me: dbt" }));
    expect(onDecide).toHaveBeenCalledWith("dbt", "no");

    rerender(
      <CoveragePanel
        coverage={coverage({ preferred: [skill({ name: "dbt", status: "added", evidence: "Added to your CV." })] })}
        onDecide={onDecide}
      />,
    );
    expect(screen.queryByRole("button", { name: "I have this: dbt" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Undo: dbt" }));
    expect(onDecide).toHaveBeenLastCalledWith("dbt", null);
  });

  it("shows matched_as and gives shown skills no buttons", () => {
    render(
      <CoveragePanel
        coverage={coverage({ required: [skill({ name: "Postgres", matched_as: "PostgreSQL" })], preferred: [] })}
        onDecide={vi.fn()}
      />,
    );

    expect(screen.getByText("Matched as PostgreSQL")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Postgres/ })).toBeNull();
  });
});
