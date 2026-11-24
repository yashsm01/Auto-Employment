import type { components } from "../types/api";
import { postJson, putJson, request } from "./client";

export type PrepView = components["schemas"]["PrepView"];
export type PrepPack = components["schemas"]["PrepPack"];
export type SourcedLine = components["schemas"]["SourcedLine"];
export type SourceLink = components["schemas"]["SourceLink"];
export type DeepSearchView = components["schemas"]["DeepSearchView"];
export type DeepSearchSettings = components["schemas"]["DeepSearchSettings"];

export const getPrep = (id: string) => request<PrepView>(`/applications/${id}/prep`);
export const runPrep = (id: string, extra: string | null) =>
  postJson<PrepView>(`/applications/${id}/prep`, { extra });
export const getDeepSearch = () => request<DeepSearchView>("/deep-search");
export const saveDeepSearch = (value: DeepSearchSettings) =>
  putJson<DeepSearchView>("/deep-search", value);
