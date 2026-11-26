import type { components } from "../types/api";
import { deleteJson, postJson, request } from "./client";

export type NearbyEmployer = components["schemas"]["NearbyEmployer"];
export type NearbyResults = components["schemas"]["NearbyResults"];
export type SavedEmployer = components["schemas"]["SavedEmployer"];
export type SavedEmployers = components["schemas"]["SavedEmployers"];
export type EmployerContacts = components["schemas"]["EmployerContacts"];

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
    rating: place.rating,
    rating_count: place.rating_count,
    hours: place.hours ?? [],
  });

export const getContacts = (id: string) =>
  request<EmployerContacts>(`/employers/${id}/contacts`);

/** Reads the employer's pages again now. Can take several seconds. */
export const refreshContacts = (id: string) =>
  postJson<EmployerContacts>(`/employers/${id}/contacts`);

export const removeEmployer = (id: string) => deleteJson<{ removed: boolean }>(`/employers/${id}`);
