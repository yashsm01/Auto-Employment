import type { components } from "../types/api";
import { postJson } from "./client";

export type RunResponse = components["schemas"]["RunResponse"];

export const runLeadSearch = () => postJson<RunResponse>("/runs/lead");

const NO_SOURCES = "No job sources";

/** Turns a run result into a summary, a how-to note, or a problem to show. */
export function describeRun(result: RunResponse): {
  summary?: string;
  info?: string;
  problem?: string;
} {
  if (result.status === "error") return { problem: result.error ?? "The search failed." };
  const output = result.output as { new_jobs?: number; shortlisted?: number; errors?: string[] };
  const errors = output.errors ?? [];
  const noSources = errors.find((error) => error.startsWith(NO_SOURCES));
  if (noSources) return { info: noSources };
  return {
    summary: `Search finished: ${output.new_jobs ?? 0} new jobs, ${output.shortlisted ?? 0} shortlisted.`,
    problem: errors.length ? `Some sources had problems: ${errors.join("; ")}` : undefined,
  };
}
