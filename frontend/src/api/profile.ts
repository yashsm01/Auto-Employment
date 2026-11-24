import type { components } from "../types/api";
import { putJson, request } from "./client";

export type ProfileView = components["schemas"]["ProfileView"];
export type ProfileUpdate = components["schemas"]["ProfileUpdate"];
export type BoardEntry = components["schemas"]["BoardEntry"];
export type SkillEntry = components["schemas"]["SkillEntry"];

export const getProfile = () => request<ProfileView>("/profile");
export const saveProfile = (body: ProfileUpdate) => putJson<ProfileView>("/profile", body);

export function uploadResume(file: File): Promise<ProfileView> {
  const form = new FormData();
  form.append("file", file);
  return request<ProfileView>("/profile/resume", { method: "POST", body: form });
}
