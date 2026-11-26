import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  decideResume,
  decideSkill,
  getReviewList,
  getTailoredResume,
  regenerateResume,
  saveCoverNote,
} from "../api/resumes";

const TAILORING_POLL_MS = 3000;

export const useReviewList = () =>
  useQuery({
    queryKey: ["resume-review"],
    queryFn: getReviewList,
    // Keep the nav count current while a resume is being tailored in the background.
    refetchInterval: (query) =>
      query.state.data?.items.some((item) => item.status === "tailoring" && !item.error)
        ? TAILORING_POLL_MS
        : false,
  });

export const useTailoredResume = (id: string) =>
  useQuery({
    queryKey: ["tailored", id],
    queryFn: () => getTailoredResume(id),
    // Check again while tailoring runs in the background, until it finishes or fails.
    refetchInterval: (query) =>
      query.state.data?.status === "tailoring" && !query.state.data.error
        ? TAILORING_POLL_MS
        : false,
  });

function useRefresh(id: string) {
  const client = useQueryClient();
  return () =>
    Promise.all(
      // An approved resume moves to the Outbox, so its list and nav count change too.
      [["tailored", id], ["resume-review"], ["pipeline"], ["application", id], ["outbox"]].map(
        (queryKey) => client.invalidateQueries({ queryKey }),
      ),
    );
}

export function useSaveCoverNote(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (note: string) => saveCoverNote(id, note),
    onSuccess: (saved) => client.setQueryData(["tailored", id], saved),
  });
}

export function useResumeDecision(id: string) {
  const refresh = useRefresh(id);
  return useMutation({
    mutationFn: (action: "approve" | "reject") => decideResume(id, action),
    onSettled: refresh,
  });
}

export function useRegenerate(id: string) {
  const refresh = useRefresh(id);
  return useMutation({ mutationFn: () => regenerateResume(id), onSettled: refresh });
}

export type SkillDecision = { skill: string; decision: "have" | "no" | null };

/** Changing a skill decision rewrites the CV, so the resume, shortlist and master CV refresh. */
export function useSkillDecision(id: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ skill, decision }: SkillDecision) => decideSkill(skill, decision),
    onSettled: () =>
      Promise.all(
        [["tailored", id], ["shortlist"], ["master-cv"]].map((queryKey) =>
          client.invalidateQueries({ queryKey }),
        ),
      ),
  });
}
