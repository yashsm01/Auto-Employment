import type { components } from "../types/api";
import { postJson, putJson, request } from "./client";

export type OutboxView = components["schemas"]["OutboxView"];
export type ToSendItem = components["schemas"]["ToSendItem"];
export type OutboxItem = components["schemas"]["OutboxItem"];
export type WaitingItem = components["schemas"]["WaitingItem"];
export type Outcome = components["schemas"]["OutcomeRequest"]["action"];

export const getOutbox = () => request<OutboxView>("/outbox");
export const queueEmail = (id: string, to: string) =>
  postJson<OutboxView>(`/applications/${id}/send`, { to });
export const markApplied = (id: string) => postJson<OutboxView>(`/applications/${id}/applied`);
export const recordOutcome = (id: string, action: Outcome) =>
  postJson<OutboxView>(`/applications/${id}/outcome`, { action });
export const cancelEmail = (id: string) => postJson<OutboxView>(`/outbox/${id}/cancel`);
export const retryEmail = (id: string) => postJson<OutboxView>(`/outbox/${id}/retry`);
export const saveDailyLimit = (limit: number) =>
  putJson<OutboxView>("/outbox/settings", { daily_send_limit: limit });
