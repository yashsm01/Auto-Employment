import type { components } from "../types/api";
import { request } from "./client";

export type Pipeline = components["schemas"]["Pipeline"];
export type BoardCard = components["schemas"]["BoardCard"];
export type Shortlist = components["schemas"]["Shortlist"];
export type ShortlistItem = components["schemas"]["ShortlistItem"];

export type ApplicationDetail = components["schemas"]["ApplicationDetail"];

export const getApplication = (id: string) => request<ApplicationDetail>(`/applications/${id}`);
export const getPipeline = () => request<Pipeline>("/pipeline");
export const getShortlist = () => request<Shortlist>("/shortlist");
