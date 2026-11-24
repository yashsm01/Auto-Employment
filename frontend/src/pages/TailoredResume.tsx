import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { apiUrl } from "../api/client";
import type { ResumeSections, TailoredResumeView } from "../api/resumes";
import { ErrorNotice, InfoNotice, SuccessNotice } from "../components/Notice";
import {
  useRegenerate,
  useResumeDecision,
  useSaveCoverNote,
  useTailoredResume,
} from "../hooks/useResumes";

const CHANGED = "border border-brand/30 bg-brand-soft";

function ResumeColumn({
  label,
  resume,
  changed,
  summaryChanged = false,
}: {
  label: string;
  resume: ResumeSections;
  changed: Set<string>;
  summaryChanged?: boolean;
}) {
  return (
    <section aria-label={label} className="card flex min-w-0 flex-col gap-3">
      <h2 className="m-0 font-display text-[17px] font-bold">{label}</h2>
      {resume.summary && (
        <p
          data-changed={summaryChanged ? "true" : "false"}
          className={`m-0 rounded-lg text-sm leading-relaxed ${summaryChanged ? `${CHANGED} px-3 py-2` : ""}`}
        >
          {resume.summary}
        </p>
      )}
      {(resume.roles ?? []).map((role) => (
        <div key={`${role.title}-${role.employer}`} className="flex flex-col gap-1">
          <b className="text-sm">
            {role.title} — {role.employer}
          </b>
          {(role.location || role.dates) && (
            <span className="text-xs text-muted">
              {[role.location, role.dates].filter(Boolean).join(" · ")}
            </span>
          )}
          <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
            {(role.bullets ?? []).map((bullet) => {
              const isChanged = changed.has(bullet.id);
              return (
                <li
                  key={bullet.id}
                  data-changed={isChanged ? "true" : "false"}
                  className={`rounded-lg px-3 py-2 text-sm leading-relaxed ${
                    isChanged ? CHANGED : "bg-page"
                  }`}
                >
                  {bullet.text}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {resume.skills && resume.skills.length > 0 && (
        <p className="m-0 text-sm">
          <b>Skills.</b> {resume.skills.join(", ")}
        </p>
      )}
    </section>
  );
}

function CoverNote({ view, editable }: { view: TailoredResumeView; editable: boolean }) {
  const [note, setNote] = useState(view.cover_note);
  const save = useSaveCoverNote(view.application_id);
  return (
    <section className="card flex flex-col gap-3">
      <h2 className="m-0 font-display text-[17px] font-bold">
        <label htmlFor="cover-note">Cover note</label>
      </h2>
      <textarea
        id="cover-note"
        className="input min-h-48 py-3 leading-relaxed"
        value={note}
        readOnly={!editable}
        onChange={(event) => setNote(event.target.value)}
      />
      {editable && (
        <div className="flex flex-wrap items-center gap-3">
          <button
            type="button"
            className="btn"
            disabled={save.isPending || !note.trim()}
            onClick={() => save.mutate(note)}
          >
            Save cover note
          </button>
          {save.isSuccess && <span className="text-sm text-ok">Cover note saved.</span>}
        </div>
      )}
      {save.error && <ErrorNotice message={save.error.message} />}
    </section>
  );
}

export default function TailoredResume() {
  const { id = "" } = useParams();
  const { data: view, error, isPending } = useTailoredResume(id);
  const decision = useResumeDecision(id);
  const regenerate = useRegenerate(id);

  if (isPending) return <p className="text-muted">Loading the tailored resume…</p>;
  if (error) return <ErrorNotice message={error.message} />;

  const changed = new Set(view.changed_ids);
  const ready = view.status === "ready";
  const problem = decision.error ?? regenerate.error;

  return (
    <>
      <Link to="/resumes" className="text-sm font-semibold text-brand-dark no-underline">
        ← Resume review
      </Link>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1.5">
          <h1 className="m-0 font-display text-[28px] font-extrabold tracking-tight">
            Resume for {view.title}
          </h1>
          <p className="m-0 text-muted">
            {view.company} ·{" "}
            <Link to={`/jobs/${view.application_id}`} className="text-brand-dark">
              open job
            </Link>
          </p>
        </div>
        <div className="flex flex-wrap gap-2.5">
          {view.pdf_url && (
            <a className="btn" href={apiUrl(view.pdf_url)} target="_blank" rel="noopener noreferrer">
              Download PDF
            </a>
          )}
          {ready && (
            <>
              <button
                type="button"
                className="btn"
                disabled={regenerate.isPending}
                onClick={() => regenerate.mutate()}
              >
                Regenerate
              </button>
              <button
                type="button"
                className="btn"
                disabled={decision.isPending}
                onClick={() => decision.mutate("reject")}
              >
                Reject
              </button>
              <button
                type="button"
                className="btn btn-primary"
                disabled={decision.isPending}
                onClick={() => decision.mutate("approve")}
              >
                Approve
              </button>
            </>
          )}
        </div>
      </header>

      {problem && <ErrorNotice message={problem.message} />}
      {view.status === "approved" && (
        <SuccessNotice message="Approved. Send it from the ">
          <Link to="/outbox" className="font-semibold text-ok underline">
            Outbox
          </Link>
          .
        </SuccessNotice>
      )}
      {view.status === "closed" && <InfoNotice message="Rejected. This job is closed." />}
      {view.status === "tailoring" &&
        (view.error ? (
          <div className="flex flex-col gap-3">
            <ErrorNotice message={`Tailoring failed: ${view.error}`} />
            <button
              type="button"
              className="btn self-start"
              disabled={regenerate.isPending}
              onClick={() => regenerate.mutate()}
            >
              Try again
            </button>
          </div>
        ) : (
          <InfoNotice message="Tailoring your resume. This usually takes under a minute." />
        ))}
      {view.resume_id && !view.ai_used && (
        <InfoNotice message="AI is not connected, so your resume was not tailored. The PDF uses your resume as it is, with a short cover note." />
      )}

      {(view.base || view.tailored) && (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,340px),1fr))] gap-4">
          {view.base && <ResumeColumn label="Your original resume" resume={view.base} changed={new Set()} />}
          {view.tailored && (
            <ResumeColumn
              label="Tailored for this job"
              resume={view.tailored}
              changed={changed}
              summaryChanged={!!view.base && view.base.summary !== view.tailored.summary}
            />
          )}
        </div>
      )}

      {view.resume_id && (
        <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,340px),1fr))] gap-4">
          <CoverNote key={view.resume_id} view={view} editable={ready} />
          <section aria-label="Fact check" className="card flex flex-col gap-3">
            <h2 className="m-0 font-display text-[17px] font-bold">Fact check</h2>
            <p className="m-0 text-[13px] text-muted">
              Every line was checked against your original resume and the job post. Highlighted
              lines were reworded for this job.
            </p>
            {view.notes.length === 0 ? (
              <p className="m-0 text-sm text-ok">Nothing needed changing back.</p>
            ) : (
              <ul className="m-0 flex flex-col gap-1.5 pl-5 text-sm">
                {view.notes.map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            )}
            <h3 className="m-0 text-sm font-bold">Employer facts used</h3>
            {view.facts_used.length === 0 ? (
              <p className="m-0 text-sm text-muted">None.</p>
            ) : (
              <ul className="m-0 flex flex-col gap-1 pl-5 text-sm">
                {view.facts_used.map((fact) => (
                  <li key={fact}>{fact}</li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </>
  );
}
