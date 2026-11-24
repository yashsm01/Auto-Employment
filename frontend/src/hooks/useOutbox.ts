import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getOutbox, type OutboxView } from "../api/outbox";

const QUEUED_POLL_MS = 15000;

export const useOutbox = () =>
  useQuery({
    queryKey: ["outbox"],
    queryFn: getOutbox,
    // While emails wait to send, check again so sent ones move along.
    refetchInterval: (query) =>
      (query.state.data?.queued.length ?? 0) > 0 ? QUEUED_POLL_MS : false,
  });

/** Every Outbox action returns the new Outbox, so the page updates straight away. */
export function useOutboxAction<T>(action: (value: T) => Promise<OutboxView>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: action,
    onSuccess: (view) => client.setQueryData(["outbox"], view),
    onSettled: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ["pipeline"] }),
        client.invalidateQueries({ queryKey: ["application"] }),
      ]),
  });
}
