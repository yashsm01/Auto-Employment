import type { components } from "../types/api";
import { apiUrl, putJson, request } from "./client";

export type MasterCV = components["schemas"]["MasterCV"];
export type MasterCVView = components["schemas"]["MasterCVView"];
export type AtsReport = components["schemas"]["AtsReport"];
export type AtsItem = components["schemas"]["AtsItem"];
export type RoleSection = components["schemas"]["RoleSection"];
export type Bullet = components["schemas"]["Bullet"];

// The editor works on a CV whose lists are always present, even when the API omits them.
export type CvRole = RoleSection & { bullets: Bullet[] };
export type CvSections = Omit<MasterCV["sections"], "roles" | "skills" | "education"> & {
  roles: CvRole[];
  skills: string[];
  education: string[];
};
export type CvDraft = Omit<MasterCV, "sections"> & { sections: CvSections };

export function toDraft(view: MasterCVView): CvDraft {
  const { sections } = view;
  return {
    contact: view.contact,
    template: view.template,
    sections: {
      ...sections,
      roles: (sections.roles ?? []).map((role) => ({ ...role, bullets: role.bullets ?? [] })),
      skills: sections.skills ?? [],
      education: sections.education ?? [],
    },
  };
}
export type Template = MasterCV["template"];

export const getMasterCv = () => request<MasterCVView>("/master-cv");
export const saveMasterCv = (cv: MasterCV) => putJson<MasterCVView>("/master-cv", cv);
export const masterCvFileUrl = (format: "pdf" | "docx") =>
  apiUrl(`/master-cv/file?format=${format}`);
