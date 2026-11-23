import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { decide, type DecisionAction } from "../api/applications";
import { getShortlist, type Shortlist, type ShortlistItem } from "../api/pipeline";

export const useShortlist = () => useQuery({ queryKey: ["shortlist"], queryFn: getShortlist });

export function useDecision() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ item, action }: { item: ShortlistItem; action: DecisionAction }) =>
      decide(item.id, action),
    onSuccess: (_result, { item }) => {
      client.setQueryData<Shortlist>(["shortlist"], (current) =>
        current
          ? { items: current.items.filter((candidate) => candidate.id !== item.id) }
          : current,
      );
    },
    onSettled: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: ["shortlist"] }),
        client.invalidateQueries({ queryKey: ["pipeline"] }),
      ]),
  });
}
