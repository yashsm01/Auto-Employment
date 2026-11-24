import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { decide, type DecisionAction } from "../api/applications";
import { getApplication } from "../api/pipeline";

export const useApplication = (id: string) =>
  useQuery({ queryKey: ["application", id], queryFn: () => getApplication(id) });

export function useApplicationDecision(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (action: DecisionAction) => decide(id, action),
    onSettled: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ["application", id] }),
        client.invalidateQueries({ queryKey: ["shortlist"] }),
        client.invalidateQueries({ queryKey: ["pipeline"] }),
        // Approving starts tailoring, so the Resume review list changes too.
        client.invalidateQueries({ queryKey: ["resume-review"] }),
        // With deep search switched on, approving also queues a preparation pack.
        client.invalidateQueries({ queryKey: ["prep", id] }),
        client.invalidateQueries({ queryKey: ["deep-search"] }),
      ]),
  });
}
