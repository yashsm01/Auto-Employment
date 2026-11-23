import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getPipeline } from "../api/pipeline";
import { runLeadSearch } from "../api/runs";

export const usePipeline = () => useQuery({ queryKey: ["pipeline"], queryFn: getPipeline });

export function useRunSearch() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: runLeadSearch,
    onSettled: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ["pipeline"] }),
        client.invalidateQueries({ queryKey: ["shortlist"] }),
      ]),
  });
}
