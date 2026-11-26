import type { components } from "../types/api";
import { postJson, putJson, request } from "./client";

export type Coverage = components["schemas"]["Coverage"];
export type SkillCoverage = components["schemas"]["SkillCoverage"];
export type ReviewItem = components["schemas"]["ReviewItem"];
export type ReviewList = components["schemas"]["ReviewList"];
export type TailoredResumeView = components["schemas"]["TailoredResumeView"];
export type ResumeSections = components["schemas"]["BaseSections"];
export type StatusResponse = components["schemas"]["StatusResponse"];

export const getReviewList = () => request<ReviewList>("/resume-review");
export const getTailoredResume = (id: string) =>
  request<TailoredResumeView>(`/applications/${id}/resume`);
export const saveCoverNote = (id: string, coverNote: string) =>
  putJson<TailoredResumeView>(`/applications/${id}/resume`, { cover_note: coverNote });
export const decideResume = (id: string, action: "approve" | "reject") =>
  postJson<StatusResponse>(`/applications/${id}/resume-decision`, { action });
export const regenerateResume = (id: string) =>
  postJson<StatusResponse>(`/applications/${id}/tailor`);
export const decideSkill = (skill: string, decision: "have" | "no" | null) =>
  postJson<{ ok: boolean }>("/skills/decision", { skill, decision });
