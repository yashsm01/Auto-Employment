import type { components } from "../types/api";
import { request } from "./client";

export type Pipeline = components["schemas"]["Pipeline"];
export type BoardCard = components["schemas"]["BoardCard"];
export type Shortlist = components["schemas"]["Shortlist"];
export type ShortlistItem = components["schemas"]["ShortlistItem"];

export const getPipeline = () => request<Pipeline>("/pipeline");
export const getShortlist = () => request<Shortlist>("/shortlist");
