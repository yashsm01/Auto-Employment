import type { components } from "../types/api";
import { postJson, putJson, request } from "./client";
import type { OutboxView } from "./outbox";

export type Phase4View = components["schemas"]["Phase4View"];
export type CallItem = components["schemas"]["CallItem"];

export const getPhase4 = () => request<Phase4View>("/settings/phase4");
export const testCall = () => postJson<Phase4View>("/calls/test");
export const testWhatsApp = () => postJson<Phase4View>("/notifications/test");
export const sendAfterCall = (id: string, to: string) =>
  postJson<OutboxView>(`/applications/${id}/send-after-call`, { to });

export type AutoModeView = components["schemas"]["AutoModeView"];
export type AutoModeSettings = components["schemas"]["AutoModeSettings"];

export const getAutoMode = () => request<AutoModeView>("/auto-mode");
export const saveAutoMode = (value: AutoModeSettings) => putJson<AutoModeView>("/auto-mode", value);

export type WhatsAppLink = components["schemas"]["WhatsAppLink"];

export const getWhatsAppLink = () => request<WhatsAppLink>("/whatsapp/status");
export const unlinkWhatsApp = () => postJson<WhatsAppLink>("/whatsapp/logout");
