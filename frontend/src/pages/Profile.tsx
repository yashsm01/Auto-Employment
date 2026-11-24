import { useRef, useState, type ChangeEvent } from "react";

import type { BoardEntry, ProfileUpdate, ProfileView, SkillEntry } from "../api/profile";
import { describeRun, type RunResponse } from "../api/runs";
import ChipEditor from "../components/ChipEditor";
import { ErrorNotice, ExampleTag, SuccessNotice } from "../components/Notice";
import { useProfile, useSaveProfile, useUploadResume } from "../hooks/useProfile";
import { useRunSearch } from "../hooks/usePipeline";

const REGIONS = ["Auckland", "Wellington", "Christchurch", "Hamilton", "Tauranga", "Dunedin", "Remote NZ"];
const PLACE_SUGGESTIONS = [
  "Ashburton", "Bay of Plenty", "Blenheim", "Canterbury", "Gisborne", "Greymouth", "Hastings",
  "Hawke's Bay", "Invercargill", "Kapiti Coast", "Levin", "Lower Hutt", "Manawatū", "Marlborough",
  "Masterton", "Napier", "Nelson", "New Plymouth", "North Shore", "Northland", "Oamaru", "Otago",
  "Palmerston North", "Porirua", "Pukekohe", "Queenstown", "Rangiora", "Rolleston", "Rotorua",
  "Southland", "Taranaki", "Tasman", "Taupō", "Te Awamutu", "Timaru", "Upper Hutt", "Waikato",
  "Wānaka", "West Coast", "Westport", "Whakatāne", "Whanganui", "Whangārei",
];
const WORK_RIGHTS = [
  ["", "Not set"],
  ["citizen", "Citizen"],
  ["resident", "Resident"],
  ["open_visa", "Open work visa"],
  ["needs_sponsorship", "Needs sponsorship"],
] as const;
const PLATFORMS = [
  ["greenhouse", "Greenhouse"],
  ["lever", "Lever"],
  ["ashby", "Ashby"],
] as const;
const BOARD_NAME = /^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$/;
const CONNECTIONS = [
  ["claude", "Claude", "Reads your resume, scores jobs, summarises employers"],
  ["gemini", "Gemini", "Ranks jobs against your profile"],
  ["trademe", "Trade Me", "NZ job listings"],
  ["gmail", "Gmail", "SEEK, LinkedIn and Indeed alert emails"],
  ["places", "Google Places", "Employer address and phone"],
  ["tavily", "Tavily", "Employer news"],
] as const;

const skillLabel = (skill: SkillEntry) =>
  skill.years ? `${skill.name} · ${skill.years} yrs` : skill.name;

const withoutValue = (items: string[], value: string) => items.filter((item) => item !== value);
const withValue = (items: string[], value: string) =>
  items.some((item) => item.toLowerCase() === value.toLowerCase()) ? items : [...items, value];

function searchMessage(result: RunResponse): { ok?: string; problem?: string } {
  const outcome = describeRun(result);
  const note = outcome.summary ?? outcome.info;
  return { ok: note ? `Saved. ${note}` : undefined, problem: outcome.problem };
}

type FormProps = {
  profile: ProfileView;
  busy: boolean;
  onSave: (body: ProfileUpdate, thenSearch: boolean) => void;
};

function ProfileForm({ profile, busy, onSave }: FormProps) {
  const [titles, setTitles] = useState(profile.titles);
  const [skills, setSkills] = useState(profile.skills);
  const [queries, setQueries] = useState(profile.search_queries);
  const [regions, setRegions] = useState(profile.regions);
  const [workRights, setWorkRights] = useState<string>(profile.work_rights ?? "");
  const [salary, setSalary] = useState(profile.salary_min?.toString() ?? "");
  const [avoid, setAvoid] = useState(profile.avoid_keywords);
  const [threshold, setThreshold] = useState(profile.shortlist_threshold);
  const [boards, setBoards] = useState(profile.boards);
  const [platform, setPlatform] = useState<BoardEntry["platform"]>("greenhouse");
  const [token, setToken] = useState("");
  const [company, setCompany] = useState("");
  const [boardError, setBoardError] = useState<string | null>(null);
  const [fullName, setFullName] = useState(profile.contact.name ?? "");
  const [email, setEmail] = useState(profile.contact.email ?? "");
  const [phone, setPhone] = useState(profile.contact.phone ?? "");

  const [customPlaces, setCustomPlaces] = useState(
    profile.regions.filter((region) => !REGIONS.includes(region)),
  );
  const [placeDraft, setPlaceDraft] = useState("");
  const regionOptions = [...REGIONS, ...customPlaces];

  const addPlace = () => {
    const value = placeDraft.trim();
    setPlaceDraft("");
    if (!value) return;
    const existing = regionOptions.find((option) => option.toLowerCase() === value.toLowerCase());
    if (!existing) setCustomPlaces([...customPlaces, value]);
    setRegions(withValue(regions, existing ?? value));
  };

  const addBoard = () => {
    const name = token.trim();
    const label = company.trim();
    if (!BOARD_NAME.test(name)) {
      setBoardError("Board name can only use letters, numbers, dots, dashes and underscores.");
      return;
    }
    if (!label) {
      setBoardError("Add the company name for this board.");
      return;
    }
    setBoardError(null);
    setBoards([...boards, { platform, token: name, company: label }]);
    setToken("");
    setCompany("");
  };

  const save = (thenSearch: boolean) =>
    onSave(
      {
        titles,
        skills,
        tools: profile.tools,
        search_queries: queries,
        regions,
        work_rights: (workRights || null) as ProfileUpdate["work_rights"],
        salary_min: salary === "" ? null : Number(salary),
        avoid_keywords: avoid,
        shortlist_threshold: threshold,
        boards,
        contact: {
          name: fullName.trim() || null,
          email: email.trim() || null,
          phone: phone.trim() || null,
        },
      },
      thenSearch,
    );

  return (
    <>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,340px),1fr))] gap-4">
        <section className="card flex flex-col gap-3">
          <h2 className="m-0 font-display text-[17px] font-bold">What was read</h2>
          <span className="label">Job titles</span>
          <ChipEditor
            addLabel="Add a job title"
            items={titles.map((title) => ({ key: title, label: title }))}
            onAdd={(value) => setTitles(withValue(titles, value))}
            onRemove={(value) => setTitles(withoutValue(titles, value))}
          />
          <span className="label">Skills</span>
          <ChipEditor
            addLabel="Add a skill"
            items={skills.map((skill) => ({ key: skill.name, label: skillLabel(skill) }))}
            onAdd={(value) =>
              setSkills(
                skills.some((skill) => skill.name.toLowerCase() === value.toLowerCase())
                  ? skills
                  : [...skills, { name: value, years: null, level: null }],
              )
            }
            onRemove={(value) => setSkills(skills.filter((skill) => skill.name !== value))}
          />
          {(profile.seniority || profile.industries.length > 0) && (
            <p className="m-0 text-sm text-muted">
              {[profile.seniority, profile.industries.join(", ")].filter(Boolean).join(" · ")}
            </p>
          )}
        </section>

        <section className="card flex flex-col gap-3">
          <h2 className="m-0 font-display text-[17px] font-bold">Search queries</h2>
          <p className="m-0 text-[13px] text-muted">
            Leave this empty to build searches from your titles, skills and regions.
          </p>
          <ChipEditor
            addLabel="Add a search"
            placeholder="e.g. API developer Wellington"
            items={queries.map((query) => ({ key: query, label: query }))}
            onAdd={(value) => setQueries(withValue(queries, value))}
            onRemove={(value) => setQueries(withoutValue(queries, value))}
          />
        </section>
      </div>

      <section className="card flex flex-col gap-4">
        <h2 className="m-0 font-display text-[17px] font-bold">Preferences</h2>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,220px),1fr))] gap-4">
          <fieldset className="col-span-full m-0 flex flex-col gap-2 border-0 p-0">
            <legend className="label mb-2 p-0">Cities, towns and regions</legend>
            <div className="flex max-w-xl gap-2">
              <label htmlFor="add-place" className="sr-only">
                Add a town or region
              </label>
              <input
                id="add-place"
                className="input min-w-0 flex-1"
                list="nz-places"
                placeholder="Add any NZ town or region, e.g. Timaru"
                value={placeDraft}
                onChange={(event) => setPlaceDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    addPlace();
                  }
                }}
              />
              <datalist id="nz-places">
                {PLACE_SUGGESTIONS.map((place) => (
                  <option key={place} value={place} />
                ))}
              </datalist>
              <button type="button" className="btn" aria-label="Add this place" onClick={addPlace}>
                Add
              </button>
            </div>
            <div className="flex flex-wrap gap-x-3 gap-y-1">
              <label className="flex min-h-9 items-center gap-1.5 text-sm font-semibold">
                <input
                  type="checkbox"
                  checked={regions.length === 0}
                  onChange={() => setRegions([])}
                />
                All of New Zealand
              </label>
              {regionOptions.map((region) => (
                <label key={region} className="flex min-h-9 items-center gap-1.5 text-sm">
                  <input
                    type="checkbox"
                    checked={regions.includes(region)}
                    onChange={(event) =>
                      setRegions(
                        event.target.checked
                          ? [...regions, region]
                          : withoutValue(regions, region),
                      )
                    }
                  />
                  {region}
                </label>
              ))}
            </div>
          </fieldset>
          <div className="flex flex-col gap-1.5">
            <label className="label" htmlFor="work-rights">
              Work rights
            </label>
            <select
              id="work-rights"
              className="input"
              value={workRights}
              onChange={(event) => setWorkRights(event.target.value)}
            >
              {WORK_RIGHTS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="label" htmlFor="salary">
              Lowest salary (NZ$ a year)
            </label>
            <input
              id="salary"
              className="input"
              type="number"
              min={0}
              value={salary}
              onChange={(event) => setSalary(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="label" htmlFor="threshold">
              Shortlist when score is at least {threshold}
            </label>
            <input
              id="threshold"
              type="range"
              min={50}
              max={95}
              step={5}
              value={threshold}
              onChange={(event) => setThreshold(Number(event.target.value))}
            />
          </div>
        </div>
        <div className="flex flex-col gap-1.5">
          <span className="label">Words to avoid in job titles</span>
          <ChipEditor
            addLabel="Add a word to avoid"
            items={avoid.map((word) => ({ key: word, label: word }))}
            onAdd={(value) => setAvoid(withValue(avoid, value))}
            onRemove={(value) => setAvoid(withoutValue(avoid, value))}
          />
        </div>
      </section>

      <section className="card flex flex-col gap-3">
        <h2 className="m-0 font-display text-[17px] font-bold">Company careers pages</h2>
        <p className="m-0 text-[13px] text-muted">
          Add companies that post jobs on Greenhouse, Lever or Ashby. The board name is the last
          part of their jobs page address.
        </p>
        {boards.map((board) => (
          <div
            key={`${board.platform}:${board.token}`}
            className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-2"
          >
            <span className="text-sm">
              <b>{board.company}</b>
              <span className="text-muted">
                {" "}
                · {board.platform} · {board.token}
              </span>
            </span>
            <button
              type="button"
              className="btn"
              aria-label={`Remove ${board.company}`}
              onClick={() => setBoards(boards.filter((item) => item !== board))}
            >
              Remove
            </button>
          </div>
        ))}
        <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,180px),1fr))] items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <label className="label" htmlFor="board-platform">
              Platform
            </label>
            <select
              id="board-platform"
              className="input"
              value={platform}
              onChange={(event) => setPlatform(event.target.value as BoardEntry["platform"])}
            >
              {PLATFORMS.map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="label" htmlFor="board-token">
              Board name
            </label>
            <input
              id="board-token"
              className="input"
              value={token}
              onChange={(event) => setToken(event.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="label" htmlFor="board-company">
              Company name
            </label>
            <input
              id="board-company"
              className="input"
              value={company}
              onChange={(event) => setCompany(event.target.value)}
            />
          </div>
          <button type="button" className="btn" onClick={addBoard}>
            Add board
          </button>
        </div>
        {boardError && <ErrorNotice message={boardError} />}
      </section>

      <section className="card flex flex-col gap-3">
        <h2 className="m-0 font-display text-[17px] font-bold">Your details for resumes</h2>
        <p className="m-0 text-[13px] text-muted">
          Shown at the top of each tailored resume. Your email and phone number are removed
          from your resume before it is sent to AI.
        </p>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,220px),1fr))] gap-4">
          <div className="flex flex-col gap-1.5">
            <label className="label" htmlFor="full-name">
              Full name
            </label>
            <input id="full-name" className="input" value={fullName} onChange={(event) => setFullName(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="label" htmlFor="contact-email">
              Email
            </label>
            <input id="contact-email" className="input" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="label" htmlFor="contact-phone">
              Phone
            </label>
            <input id="contact-phone" className="input" type="tel" value={phone} onChange={(event) => setPhone(event.target.value)} />
          </div>
        </div>
      </section>

      <section className="card flex flex-col gap-2">
        <h2 className="m-0 font-display text-[17px] font-bold">Connections</h2>
        <p className="m-0 text-[13px] text-muted">
          Keys are kept in the backend's .env file, never in this page.
        </p>
        {CONNECTIONS.map(([key, name, purpose]) => (
          <div key={key} className="flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-line pt-2 text-sm">
            <span className="font-semibold">{name}</span>
            <span className="flex-1 text-[13px] text-muted">{purpose}</span>
            <span className={profile.connections[key] ? "font-semibold text-ok" : "text-muted"}>
              {profile.connections[key] ? "Connected" : "Not connected"}
            </span>
          </div>
        ))}
      </section>

      <div className="flex flex-wrap gap-2.5">
        <button type="button" className="btn" disabled={busy} onClick={() => save(false)}>
          Save
        </button>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => save(true)}>
          {busy ? "Working…" : "Save and run search"}
        </button>
      </div>
    </>
  );
}

export default function Profile() {
  const { data, error, isPending } = useProfile();
  const saveMutation = useSaveProfile();
  const uploadMutation = useUploadResume();
  const searchMutation = useRunSearch();
  const fileInput = useRef<HTMLInputElement>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  // The form reloads only after a save or upload, so a background refresh keeps unsaved edits.
  const [formVersion, setFormVersion] = useState(0);

  if (isPending) return <p className="text-muted">Loading your profile…</p>;
  if (error) return <ErrorNotice message={error.message} />;

  const busy = saveMutation.isPending || uploadMutation.isPending || searchMutation.isPending;

  const resetNotices = () => {
    setMessage(null);
    setProblem(null);
  };

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    resetNotices();
    try {
      const saved = await uploadMutation.mutateAsync(file);
      setFormVersion((version) => version + 1);
      setMessage(saved.warning ?? "Resume read. Check the details below, then save.");
    } catch (failure) {
      setProblem((failure as Error).message);
    }
  };

  const handleSave = async (body: ProfileUpdate, thenSearch: boolean) => {
    resetNotices();
    try {
      await saveMutation.mutateAsync(body);
      setFormVersion((version) => version + 1);
      if (!thenSearch) {
        setMessage("Profile saved.");
        return;
      }
      const result: RunResponse = await searchMutation.mutateAsync();
      const outcome = searchMessage(result);
      setMessage(outcome.ok ?? null);
      setProblem(outcome.problem ?? null);
    } catch (failure) {
      setProblem((failure as Error).message);
    }
  };

  return (
    <>
      <header className="flex flex-col items-start gap-1.5">
        {data.is_example && <ExampleTag />}
        <h1 className="m-0 font-display text-[28px] font-extrabold tracking-tight">
          My resume profile
        </h1>
        <p className="m-0 text-muted">
          Your resume decides what we search for and how jobs are scored. Check what was read, then
          edit anything that is wrong.
        </p>
      </header>

      {message && <SuccessNotice message={message} />}
      {problem && <ErrorNotice message={problem} />}

      <section className="card flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-col gap-1">
          <b className="text-[15px]">{data.filename ?? "No resume uploaded"}</b>
          <span className="text-[13px] text-muted">
            {data.is_example
              ? "Upload your resume to replace this example and remove the example jobs."
              : "Your base resume. PDF or Word, up to 5 MB."}
          </span>
        </div>
        <input
          ref={fileInput}
          aria-label="Upload resume"
          className="sr-only"
          type="file"
          accept=".pdf,.docx"
          disabled={busy}
          onChange={handleFile}
        />
        <button
          type="button"
          className="btn"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
        >
          {uploadMutation.isPending ? "Reading…" : "Choose resume file"}
        </button>
      </section>

      <ProfileForm key={formVersion} profile={data} busy={busy} onSave={handleSave} />
    </>
  );
}
