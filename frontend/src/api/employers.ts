import type { components } from "../types/api";
import { deleteJson, postJson, request } from "./client";

export type NearbyEmployer = components["schemas"]["NearbyEmployer"];
export type NearbyResults = components["schemas"]["NearbyResults"];
export type SavedEmployer = components["schemas"]["SavedEmployer"];
export type SavedEmployers = components["schemas"]["SavedEmployers"];

export const searchEmployers = (business: string, town: string) =>
  postJson<NearbyResults>("/employers/search", { business, town });

export const listEmployers = () => request<SavedEmployers>("/employers");

export const saveEmployer = (place: NearbyEmployer) =>
  postJson<SavedEmployer>("/employers", {
    place_id: place.place_id,
    name: place.name,
    address: place.address,
    phone: place.phone,
    website: place.website,
    lat: place.lat,
    lng: place.lng,
  });

export const removeEmployer = (id: string) => deleteJson<{ removed: boolean }>(`/employers/${id}`);
