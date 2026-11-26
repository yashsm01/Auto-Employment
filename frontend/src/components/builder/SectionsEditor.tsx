import type { CvDraft, CvRole, MasterCV } from "../../api/masterCv";
import ChipEditor from "../ChipEditor";

// Limits the server enforces on a saved CV (backend app/schemas/master_cv.py).
const MAX_ROLES = 20;
const MAX_BULLETS = 20;
const MAX_SKILLS = 80;
const MAX_EDUCATION = 20;

export type CvUpdater = (change: (cv: CvDraft) => CvDraft) => void;

type Props = {
  draft: CvDraft;
  update: CvUpdater;
};

const newId = () => `b-${Math.random().toString(36).slice(2, 10)}`;
const emptyToNull = (value: string) => (value === "" ? null : value);
const withoutIndex = <T,>(items: T[], index: number) =>
  items.filter((_, position) => position !== index);
const moved = <T,>(items: T[], index: number, delta: number): T[] => {
  const target = index + delta;
  if (target < 0 || target >= items.length) return items;
  const next = [...items];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
};
const wordCount = (text: string) => text.trim().split(/\s+/).filter(Boolean).length;

const inputClass = "input w-full";
const sectionClass = "card flex flex-col gap-3";
const headingClass = "m-0 font-display text-[17px] font-bold";
const buttonClass = "btn";

const CONTACT_FIELDS: [keyof MasterCV["contact"], string, string][] = [
  ["name", "Name", "text"],
  ["email", "Email", "email"],
  ["phone", "Phone", "tel"],
  ["location", "City", "text"],
  ["linkedin", "LinkedIn", "text"],
  ["whatsapp", "WhatsApp", "tel"],
  ["work_rights", "Work rights", "text"],
];

export default function SectionsEditor({ draft, update }: Props) {
  const { contact, sections } = draft;

  const changeSections = (change: (current: CvDraft["sections"]) => CvDraft["sections"]) =>
    update((cv) => ({ ...cv, sections: change(cv.sections) }));
  const changeRoles = (change: (roles: CvRole[]) => CvRole[]) =>
    changeSections((current) => ({ ...current, roles: change(current.roles) }));
  const changeRole = (index: number, change: (role: CvRole) => CvRole) =>
    changeRoles((roles) => roles.map((role, position) => (position === index ? change(role) : role)));
  const changeContact = (field: keyof MasterCV["contact"], value: string) =>
    update((cv) => ({ ...cv, contact: { ...cv.contact, [field]: emptyToNull(value) } }));

  return (
    <div className="flex flex-col gap-4">
      <section className={sectionClass}>
        <h2 className={headingClass}>Your details</h2>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,220px),1fr))] gap-4">
          {CONTACT_FIELDS.map(([field, label, type]) => (
            <div key={field} className="flex flex-col gap-1.5">
              <label className="label" htmlFor={`cv-${field}`}>
                {label}
              </label>
              <input
                id={`cv-${field}`}
                type={type}
                className={inputClass}
                value={contact[field] ?? ""}
                onChange={(event) => changeContact(field, event.target.value)}
              />
            </div>
          ))}
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="label" htmlFor="cv-headline">
            Headline
          </label>
          <input
            id="cv-headline"
            className={inputClass}
            value={sections.headline}
            onChange={(event) =>
              changeSections((current) => ({ ...current, headline: event.target.value }))
            }
          />
        </div>
      </section>

      <section className={sectionClass}>
        <h2 className={headingClass}>Profile</h2>
        <div className="flex flex-col gap-1.5">
          <label className="label" htmlFor="cv-summary">
            Profile
          </label>
          <textarea
            id="cv-summary"
            className={`${inputClass} min-h-28`}
            value={sections.summary}
            onChange={(event) =>
              changeSections((current) => ({ ...current, summary: event.target.value }))
            }
          />
          <span className="text-[13px] text-muted">{wordCount(sections.summary)} words</span>
        </div>
      </section>

      <section className={sectionClass}>
        <h2 className={headingClass}>Key skills</h2>
        <ChipEditor
          addLabel="Add a key skill"
          items={sections.skills.map((skill) => ({ key: skill, label: skill }))}
          onAdd={(value) =>
            changeSections((current) =>
              current.skills.length >= MAX_SKILLS ||
              current.skills.some((skill) => skill.toLowerCase() === value.toLowerCase())
                ? current
                : { ...current, skills: [...current.skills, value] },
            )
          }
          onRemove={(value) =>
            changeSections((current) => ({
              ...current,
              skills: current.skills.filter((skill) => skill !== value),
            }))
          }
        />
      </section>

      <section className={sectionClass}>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className={headingClass}>Work history</h2>
          <button
            type="button"
            className={buttonClass}
            disabled={sections.roles.length >= MAX_ROLES}
            onClick={() =>
              changeRoles((roles) => [
                ...roles,
                { title: "", employer: "", location: "", dates: "", bullets: [] },
              ])
            }
          >
            Add role
          </button>
        </div>
        {sections.roles.length === 0 && (
          <p className="m-0 text-sm text-muted">No roles yet. Add one to start your work history.</p>
        )}
        {sections.roles.map((role, index) => {
          const number = index + 1;
          const roleField = (
            name: "title" | "employer" | "location" | "dates",
            label: string,
          ) => (
            <div className="flex flex-col gap-1.5">
              <label className="label" htmlFor={`role-${index}-${name}`}>
                {label}
              </label>
              <input
                id={`role-${index}-${name}`}
                aria-label={`Work history role ${number} ${label.toLowerCase()}`}
                className={inputClass}
                value={role[name]}
                onChange={(event) =>
                  changeRole(index, (current) => ({ ...current, [name]: event.target.value }))
                }
              />
            </div>
          );
          return (
            <div
              key={`role-${index}`}
              className="flex flex-col gap-3 rounded-xl border border-line p-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="m-0 text-sm font-semibold">Role {number}</h3>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className={buttonClass}
                    aria-label={`Move role ${number} up`}
                    disabled={index === 0}
                    onClick={() => changeRoles((roles) => moved(roles, index, -1))}
                  >
                    Up
                  </button>
                  <button
                    type="button"
                    className={buttonClass}
                    aria-label={`Move role ${number} down`}
                    disabled={index === sections.roles.length - 1}
                    onClick={() => changeRoles((roles) => moved(roles, index, 1))}
                  >
                    Down
                  </button>
                  <button
                    type="button"
                    className={buttonClass}
                    aria-label={`Remove role ${number}`}
                    onClick={() => changeRoles((roles) => withoutIndex(roles, index))}
                  >
                    Remove role
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,200px),1fr))] gap-3">
                {roleField("title", "Job title")}
                {roleField("employer", "Employer")}
                {roleField("location", "Location")}
                {roleField("dates", "Dates")}
              </div>
              <div className="flex flex-col gap-2">
                <span className="label">Bullets</span>
                {role.bullets.map((bullet, position) => (
                  <div key={bullet.id} className="flex gap-2">
                    <textarea
                      aria-label={`Role ${number} bullet ${position + 1}`}
                      className={`${inputClass} min-h-16`}
                      value={bullet.text}
                      onChange={(event) =>
                        changeRole(index, (current) => ({
                          ...current,
                          bullets: current.bullets.map((item) =>
                            item.id === bullet.id ? { ...item, text: event.target.value } : item,
                          ),
                        }))
                      }
                    />
                    <div className="flex shrink-0 flex-col gap-1">
                      <button
                        type="button"
                        className={buttonClass}
                        aria-label={`Move bullet ${position + 1} of role ${number} up`}
                        disabled={position === 0}
                        onClick={() =>
                          changeRole(index, (current) => ({
                            ...current,
                            bullets: moved(current.bullets, position, -1),
                          }))
                        }
                      >
                        Up
                      </button>
                      <button
                        type="button"
                        className={buttonClass}
                        aria-label={`Move bullet ${position + 1} of role ${number} down`}
                        disabled={position === role.bullets.length - 1}
                        onClick={() =>
                          changeRole(index, (current) => ({
                            ...current,
                            bullets: moved(current.bullets, position, 1),
                          }))
                        }
                      >
                        Down
                      </button>
                      <button
                        type="button"
                        className={buttonClass}
                        aria-label={`Remove bullet ${position + 1} of role ${number}`}
                        onClick={() =>
                          changeRole(index, (current) => ({
                            ...current,
                            bullets: withoutIndex(current.bullets, position),
                          }))
                        }
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
                <div>
                  <button
                    type="button"
                    className={buttonClass}
                    disabled={role.bullets.length >= MAX_BULLETS}
                    onClick={() =>
                      changeRole(index, (current) => ({
                        ...current,
                        bullets: [...current.bullets, { id: newId(), text: "" }],
                      }))
                    }
                  >
                    Add bullet to role {number}
                  </button>
                </div>
              </div>
            </div>
          );
        })}
      </section>

      <section className={sectionClass}>
        <h2 className={headingClass}>Education and certifications</h2>
        {sections.education.map((line, index) => (
          <div key={`education-${index}`} className="flex gap-2">
            <input
              aria-label={`Education line ${index + 1}`}
              className={inputClass}
              value={line}
              onChange={(event) =>
                changeSections((current) => ({
                  ...current,
                  education: current.education.map((item, position) =>
                    position === index ? event.target.value : item,
                  ),
                }))
              }
            />
            <button
              type="button"
              className={buttonClass}
              aria-label={`Remove education line ${index + 1}`}
              onClick={() =>
                changeSections((current) => ({
                  ...current,
                  education: withoutIndex(current.education, index),
                }))
              }
            >
              Remove
            </button>
          </div>
        ))}
        <div>
          <button
            type="button"
            className={buttonClass}
            disabled={sections.education.length >= MAX_EDUCATION}
            onClick={() =>
              changeSections((current) => ({ ...current, education: [...current.education, ""] }))
            }
          >
            Add education line
          </button>
        </div>
      </section>

      <section className={sectionClass}>
        <h2 className={headingClass}>Interests</h2>
        <div className="flex flex-col gap-1.5">
          <label className="label" htmlFor="cv-interests">
            Interests
          </label>
          <input
            id="cv-interests"
            className={inputClass}
            value={sections.interests}
            onChange={(event) =>
              changeSections((current) => ({ ...current, interests: event.target.value }))
            }
          />
        </div>
      </section>

      <section className={sectionClass}>
        <h2 className={headingClass}>Referees</h2>
        <div className="flex flex-col gap-1.5">
          <label className="label" htmlFor="cv-referees">
            Referees
          </label>
          <input
            id="cv-referees"
            className={inputClass}
            value={sections.referees}
            onChange={(event) =>
              changeSections((current) => ({ ...current, referees: event.target.value }))
            }
          />
        </div>
      </section>
    </div>
  );
}
