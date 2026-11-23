import type { components } from "../types/api";
import { postJson } from "./client";

export type RunResponse = components["schemas"]["RunResponse"];

export const runLeadSearch = () => postJson<RunResponse>("/runs/lead");
