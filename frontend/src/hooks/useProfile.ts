import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getProfile, saveProfile, uploadResume, type ProfileView } from "../api/profile";

export const useProfile = () => useQuery({ queryKey: ["profile"], queryFn: getProfile });

export function useSaveProfile() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: saveProfile,
    onSuccess: (saved: ProfileView) => client.setQueryData(["profile"], saved),
  });
}

export function useUploadResume() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: uploadResume,
    onSuccess: async (saved: ProfileView) => {
      client.setQueryData(["profile"], saved);
      // The first real resume removes the example jobs.
      await Promise.all([
        client.invalidateQueries({ queryKey: ["pipeline"] }),
        client.invalidateQueries({ queryKey: ["shortlist"] }),
      ]);
    },
  });
}
