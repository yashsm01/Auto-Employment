import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import type { ApplicationDetail } from "../api/pipeline";
import { ErrorNotice, ExampleTag } from "../components/Notice";
import { useApplication, useApplicationDecision } from "../hooks/useApplication";

const TABS = ["Match", "Employer", "Contact history"] as const;
type Tab = (typeof TABS)[number];

const STATUS_LABELS: Record<string, string> = {
  tailoring: "Waiting for resume tailoring",
  ready: "Resume ready for review",
  approved: "Approved to send",
  sent: "Sent",
  followed_up: "Followed up",
  replied: "Replied",
  closed: "Closed",
};
const EVENT_LABELS: Record<string, string> = {
  found: "Found",
  shortlisted: "Shortlisted",
  approved: "Approved",
  skipped: "Skipped",
  emailed: "Emailed",
  replied: "Replied",
  called: "Called",
  note: "Note",
};
const FIELD_LABELS: Record<string, string> = {
  about: "About",
  address: "Address",
  email: "Email",
  phone: "Phone",
  recent_news: "Recent news",
  website: "Website",
};
const SOURCE_LABELS: Record<string, string> = {
  job_post: "Job post",
  nzbn: "NZBN",
  places: "Google Places",
  website: "Company website",
  tavily: "Tavily",
  manual: "Added by you",
};
const CONFIDENCE: Record<string, { label: string; className: string }> = {
  high: { label: "High", className: "bg-ok-soft text-ok" },
  medium: { label: "Medium", className: "bg-column text-slate" },
  check: { label: "Check", className: "bg-warn-soft text-warn" },
};
const timeFormat = new Intl.DateTimeFormat("en-NZ", { dateStyle: "medium", timeStyle: "short" });

function MatchTab({ job }: { job: ApplicationDetail }) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,320px),1fr))] gap-4">
      <section className="card flex flex-col gap-3">
        <h2 className="m-0 font-display text-[17px] font-bold">Why it matches your resume</h2>
        <p className="m-0 text-[15px] leading-relaxed">{job.reason}</p>
        <div className="flex flex-wrap gap-1.5">
          {job.matched_skills.map((skill) => (
            <span key={skill} className="rounded-md bg-ok-soft px-2 py-0.5 text-xs text-ok">
              {skill}
            </span>
          ))}
          {job.missing_skills.map((skill) => (
            <span key={skill} className="rounded-md bg-bad-soft px-2 py-0.5 text-xs text-bad">
              Missing: {skill}
            </span>
          ))}
        </div>
        {job.similarity !== null && (
          <span className="text-[13px] text-muted">
            Resume similarity {job.similarity.toFixed(2)}
          </span>
        )}
      </section>
      <section className="card flex flex-col gap-3">
        <h2 className="m-0 font-display text-[17px] font-bold">Job description</h2>
        <p className="m-0 max-h-96 overflow-y-auto text-[15px] leading-relaxed whitespace-pre-line">
          {job.description || "The source did not include a description."}
        </p>
        {job.url && (
          <a
            className="text-sm font-semibold text-brand-dark"
            href={job.url}
            target="_blank"
            rel="noopener noreferrer"
          >
            View original post
          </a>
        )}
      </section>
    </div>
  );
}

function EmployerTab({ job }: { job: ApplicationDetail }) {
  const { employer } = job;
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,320px),1fr))] gap-4">
      <section className="card flex flex-col gap-3">
        <h2 className="m-0 font-display text-[17px] font-bold">{employer.name}</h2>
        <p className="m-0 text-[15px] leading-relaxed">
          {employer.about ?? "No company summary yet."}
        </p>
        {employer.address && <span className="text-sm">{employer.address}</span>}
        {employer.phone && <span className="text-sm">{employer.phone}</span>}
        <div className="flex flex-wrap gap-4 text-sm font-semibold">
          <a
            className="text-brand-dark"
            href={employer.map_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Open in Google Maps
          </a>
          {employer.website && (
            <a
              className="text-brand-dark"
              href={employer.website}
              target="_blank"
              rel="noopener noreferrer"
            >
              Company website
            </a>
          )}
        </div>
      </section>
      <section className="card flex flex-col gap-2">
        <h2 className="m-0 font-display text-[17px] font-bold">Employer facts</h2>
        {employer.facts.length === 0 && (
          <p className="m-0 text-sm text-muted">No facts collected yet.</p>
        )}
        {employer.facts.map((fact) => {
          const confidence = CONFIDENCE[fact.confidence] ?? CONFIDENCE.check;
          return (
            <div
              key={`${fact.field}:${fact.source}:${fact.value}`}
              className="grid grid-cols-[110px_minmax(0,1fr)] gap-2.5 border-t border-line pt-2 text-sm"
            >
              <span className="text-muted">{FIELD_LABELS[fact.field] ?? fact.field}</span>
              <div className="flex min-w-0 flex-col gap-1">
                <span className="wrap-anywhere">{fact.value}</span>
                <div className="flex flex-wrap items-center gap-1.5">
                  <span className="rounded-md bg-column px-1.5 py-0.5 text-[11px] font-semibold text-slate">
                    {SOURCE_LABELS[fact.source] ?? fact.source}
                  </span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${confidence.className}`}
                  >
                    {confidence.label}
                  </span>
                  {fact.source_url && (
                    <a
                      className="text-xs text-brand-dark"
                      href={fact.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={`Source for ${FIELD_LABELS[fact.field] ?? fact.field}`}
                    >
                      Source
                    </a>
                  )}
                </div>
              </div>
            </div>
          );
        })}
        <p className="m-0 text-[13px] text-muted">
          “Check” means one weak source. Confirm it before using it.
        </p>
      </section>
    </div>
  );
}

function HistoryTab({ job }: { job: ApplicationDetail }) {
  return (
    <section className="card flex max-w-3xl flex-col gap-3">
      <h2 className="m-0 font-display text-[17px] font-bold">Contact history</h2>
      <ol className="m-0 flex list-none flex-col gap-3 p-0">
        {job.timeline.map((event) => (
          <li key={`${event.type}:${event.created_at}`} className="flex gap-3">
            <span className="mt-1 size-3 flex-none rounded-full bg-ok" aria-hidden="true" />
            <span className="flex flex-col">
              <b className="text-sm">{EVENT_LABELS[event.type] ?? event.type}</b>
              <span className="text-[13px] text-muted">
                {timeFormat.format(new Date(event.created_at))}
              </span>
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

export default function JobDetail() {
  const { id = "" } = useParams();
  const { data: job, error, isPending } = useApplication(id);
  const decision = useApplicationDecision(id);
  const [tab, setTab] = useState<Tab>("Match");

  if (isPending) return <p className="text-muted">Loading this job…</p>;
  if (error) return <ErrorNotice message={error.message} />;

  const statusLabel = STATUS_LABELS[job.status];

  return (
    <>
      <Link to="/shortlist" className="text-sm font-semibold text-brand-dark no-underline">
        ← Back to shortlist
      </Link>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            {job.is_example && <ExampleTag />}
            <span className="rounded-full bg-column px-2.5 py-0.5 text-xs font-semibold text-slate">
              {job.source}
            </span>
            {job.score !== null && (
              <span className="rounded-full bg-brand-soft px-2.5 py-0.5 text-xs font-semibold text-brand-dark">
                Score {job.score}
              </span>
            )}
            {statusLabel && (
              <span className="rounded-full bg-warn-soft px-2.5 py-0.5 text-xs font-semibold text-warn">
                {statusLabel}
              </span>
            )}
          </div>
          <h1 className="m-0 font-display text-[28px] font-extrabold tracking-tight">
            {job.title}
          </h1>
          <p className="m-0 text-muted">
            {job.employer.name} · {job.location || job.city} · {job.salary}
          </p>
        </div>
        {job.status === "shortlisted" && (
          <div className="flex flex-wrap gap-2.5">
            <button
              type="button"
              className="btn"
              disabled={decision.isPending}
              onClick={() => decision.mutate("skip")}
            >
              Skip
            </button>
            <button
              type="button"
              className="btn btn-primary"
              disabled={decision.isPending}
              onClick={() => decision.mutate("approve")}
            >
              Approve
            </button>
          </div>
        )}
      </header>

      {decision.error && <ErrorNotice message={decision.error.message} />}
      {["tailoring", "ready", "approved"].includes(job.status) && (
        <Link to={`/jobs/${job.id}/resume`} className="btn self-start">
          View tailored resume
        </Link>
      )}

      <div
        role="tablist"
        aria-label="Job sections"
        className="inline-flex flex-wrap gap-1 self-start rounded-xl bg-column p-1"
      >
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            className={`min-h-11 cursor-pointer rounded-lg border-0 px-4 text-sm font-semibold ${
              tab === name ? "bg-white text-brand-dark shadow-sm" : "bg-transparent text-muted"
            }`}
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </div>

      {tab === "Match" && <MatchTab job={job} />}
      {tab === "Employer" && <EmployerTab job={job} />}
      {tab === "Contact history" && <HistoryTab job={job} />}
    </>
  );
}
