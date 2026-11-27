import type { components } from "../types/api";
import { postJson, putJson, request } from "./client";

export type OutboxView = components["schemas"]["OutboxView"];
export type ToSendItem = components["schemas"]["ToSendItem"];
export type OutboxItem = components["schemas"]["OutboxItem"];
export type WaitingItem = components["schemas"]["WaitingItem"];
export type FollowUpMode = components["schemas"]["FollowUpSettings"]["mode"];
export type Outcome = components["schemas"]["OutcomeRequest"]["action"];

export type ContactRow = components["schemas"]["ContactRow"];
export type AdvertContact = components["schemas"]["AdvertContact"];

export const getOutbox = () => request<OutboxView>("/outbox");
export const getOutboxContacts = () =>
  request<components["schemas"]["OutboxContacts"]>("/outbox/contacts");
export const findContacts = (applicationId: string) =>
  postJson<ContactRow>(`/applications/${applicationId}/find-contacts`);
export const queueEmail = (id: string, to: string) =>
  postJson<OutboxView>(`/applications/${id}/send`, { to });
export const markApplied = (id: string) => postJson<OutboxView>(`/applications/${id}/applied`);
export const recordOutcome = (id: string, action: Outcome) =>
  postJson<OutboxView>(`/applications/${id}/outcome`, { action });
export const cancelEmail = (id: string) => postJson<OutboxView>(`/outbox/${id}/cancel`);
export const sendDraft = (id: string) => postJson<OutboxView>(`/outbox/${id}/send`);
export const retryEmail = (id: string) => postJson<OutboxView>(`/outbox/${id}/retry`);
export const saveDailyLimit = (limit: number) =>
  putJson<OutboxView>("/outbox/settings", { daily_send_limit: limit });
export const getFollowUps = () => request<components["schemas"]["FollowUpSettings"]>("/settings/follow-ups");
export const saveFollowUps = (mode: FollowUpMode) =>
  putJson<components["schemas"]["FollowUpSettings"]>("/settings/follow-ups", { mode });
