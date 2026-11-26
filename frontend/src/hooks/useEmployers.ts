import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  listEmployers,
  refreshContacts,
  removeEmployer,
  saveEmployer,
  searchEmployers,
  type NearbyEmployer,
  type SavedEmployers,
} from "../api/employers";

export const useSavedEmployers = () =>
  useQuery({ queryKey: ["employers"], queryFn: listEmployers });

export const useEmployerSearch = () =>
  useMutation({
    mutationFn: ({ business, town }: { business: string; town: string }) =>
      searchEmployers(business, town),
  });

export function useSaveEmployer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (place: NearbyEmployer) => saveEmployer(place),
    onSettled: () => client.invalidateQueries({ queryKey: ["employers"] }),
  });
}

export function useRefreshContacts() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => refreshContacts(id),
    onSuccess: (contacts, id) =>
      client.setQueryData<SavedEmployers>(["employers"], (current) =>
        current
          ? {
              ...current,
              items: current.items.map((employer) =>
                employer.id === id ? { ...employer, contacts } : employer,
              ),
            }
          : current,
      ),
    onSettled: () => client.invalidateQueries({ queryKey: ["employers"] }),
  });
}

export function useRemoveEmployer() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => removeEmployer(id),
    onSettled: () => client.invalidateQueries({ queryKey: ["employers"] }),
  });
}
