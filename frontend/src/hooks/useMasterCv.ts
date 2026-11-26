import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../api/client";
import { getMasterCv, saveMasterCv, type MasterCVView } from "../api/masterCv";

// A 4xx answer (such as "upload your resume first") will not change on retry.
const retryServerProblems = (failures: number, error: Error) =>
  !(error instanceof ApiError && error.status >= 400 && error.status < 500) && failures < 2;

export const useMasterCv = () =>
  useQuery({ queryKey: ["master-cv"], queryFn: getMasterCv, retry: retryServerProblems });

export function useSaveMasterCv() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: saveMasterCv,
    onSuccess: (saved: MasterCVView) => client.setQueryData(["master-cv"], saved),
  });
}
