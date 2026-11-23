import type { components } from "../types/api";
import { postJson } from "./client";

export type DecisionResponse = components["schemas"]["DecisionResponse"];
export type DecisionAction = components["schemas"]["DecisionRequest"]["action"];

export const decide = (id: string, action: DecisionAction) =>
  postJson<DecisionResponse>(`/applications/${id}/decision`, { action });
