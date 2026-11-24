import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  type DeepSearchSettings,
  getDeepSearch,
  getPrep,
  runPrep,
  saveDeepSearch,
} from "../api/prep";

const RUNNING_POLL_MS = 3000;

export const usePrep = (id: string) =>
  useQuery({
    queryKey: ["prep", id],
    queryFn: () => getPrep(id),
    // Check again while the deep search waits or runs in the background.
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.status ?? "") ? RUNNING_POLL_MS : false,
  });

export function useRunPrep(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (extra: string | null) => runPrep(id, extra),
    onSuccess: (view) => client.setQueryData(["prep", id], view),
    onSettled: () => client.invalidateQueries({ queryKey: ["deep-search"] }),
  });
}

export const useDeepSearch = () => useQuery({ queryKey: ["deep-search"], queryFn: getDeepSearch });

export function useSaveDeepSearch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (value: DeepSearchSettings) => saveDeepSearch(value),
    onSuccess: (saved) => client.setQueryData(["deep-search"], saved),
  });
}
