import { useState } from "react";
import { Link } from "react-router-dom";

import type { DecisionAction } from "../api/applications";
import type { ShortlistItem } from "../api/pipeline";
import { ErrorNotice, ExampleTag, SuccessNotice } from "../components/Notice";
import { useDecision, useShortlist } from "../hooks/useShortlist";

const ALL = "All";
const HIGH = "Score 80+";
const HIGH_SCORE = 80;

function matchesFilter(item: ShortlistItem, filter: string): boolean {
  if (filter === ALL) return true;
  if (filter === HIGH) return item.score >= HIGH_SCORE;
  return item.city === filter;
}

function JobCard({
  item,
  busy,
  onDecide,
}: {
  item: ShortlistItem;
  busy: boolean;
  onDecide: (action: DecisionAction) => void;
}) {
  return (
    <article className="card flex flex-wrap items-center gap-4">
      <div className="grid size-14 flex-none place-items-center rounded-[14px] bg-brand-soft font-display text-xl font-extrabold text-brand-dark">
        <span className="sr-only">Match score </span>
        {item.score}
      </div>
      <div className="flex min-w-0 flex-[1_1_320px] flex-col gap-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="m-0 text-base font-bold">{item.title}</h2>
          <span className="rounded-full bg-column px-2.5 py-0.5 text-xs font-semibold text-slate">
            {item.source}
          </span>
        </div>
        <span className="text-sm text-muted">
          {item.company} · {item.city} · {item.salary}
        </span>
        <div className="flex flex-wrap gap-1.5">
          {item.matched_skills.map((skill) => (
            <span key={skill} className="rounded-md bg-ok-soft px-2 py-0.5 text-xs text-ok">
              {skill}
            </span>
          ))}
          {item.missing_skills.map((skill) => (
            <span key={skill} className="rounded-md bg-bad-soft px-2 py-0.5 text-xs text-bad">
              Missing: {skill}
            </span>
          ))}
        </div>
        <span className="text-[13px] text-muted">{item.reason}</span>
      </div>
      <div className="flex flex-wrap gap-2">
        <Link className="btn" to={`/jobs/${item.id}`} aria-label={`Open ${item.title}`}>
          Open
        </Link>
        {item.url && (
          <a className="btn" href={item.url} target="_blank" rel="noopener noreferrer">
            View post
          </a>
        )}
        <button
          type="button"
          className="btn"
          disabled={busy}
          aria-label={`Skip ${item.title}`}
          onClick={() => onDecide("skip")}
        >
          Skip
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy}
          aria-label={`Approve ${item.title}`}
          onClick={() => onDecide("approve")}
        >
          Approve
        </button>
      </div>
    </article>
  );
}

export default function Shortlist() {
  const { data, error, isPending } = useShortlist();
  const decision = useDecision();
  const [selected, setSelected] = useState(ALL);
  const [message, setMessage] = useState<string | null>(null);

  if (isPending) return <p className="text-muted">Loading your shortlist…</p>;
  if (error) return <ErrorNotice message={error.message} />;

  const cities = [...new Set(data.items.map((item) => item.city))];
  const filters = [ALL, HIGH, ...cities];
  const active = filters.includes(selected) ? selected : ALL;
  const visible = data.items.filter((item) => matchesFilter(item, active));

  const handleDecision = (item: ShortlistItem, action: DecisionAction) => {
    setMessage(null);
    decision.mutate(
      { item, action },
      {
        onSuccess: () =>
          setMessage(
            action === "approve"
              ? `Approved ${item.title}. It is waiting for resume tailoring.`
              : `Skipped ${item.title}.`,
          ),
      },
    );
  };

  return (
    <>
      <header className="flex flex-col items-start gap-1.5">
        {data.items.some((item) => item.is_example) && <ExampleTag />}
        <h1 className="m-0 font-display text-[28px] font-extrabold tracking-tight">Shortlist</h1>
        <p className="m-0 text-muted">
          Jobs that scored well against your resume. Approve to tailor a resume, or skip to pass.
        </p>
      </header>

      {message && <SuccessNotice message={message} />}
      {decision.error && <ErrorNotice message={decision.error.message} />}

      {data.items.length === 0 ? (
        <p className="card m-0 text-muted">
          No jobs on your shortlist right now. Run a search from the Pipeline page.
        </p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2">
            {filters.map((filter) => (
              <button
                key={filter}
                type="button"
                aria-pressed={filter === active}
                className={`chip ${filter === active ? "chip-on" : ""}`}
                onClick={() => setSelected(filter)}
              >
                {filter}
              </button>
            ))}
            <span className="ml-auto text-[13px] text-muted">{visible.length} shown</span>
          </div>
          <div className="flex flex-col gap-3">
            {visible.map((item) => (
              <JobCard
                key={item.id}
                item={item}
                busy={decision.isPending && decision.variables?.item.id === item.id}
                onDecide={(action) => handleDecision(item, action)}
              />
            ))}
          </div>
        </>
      )}
    </>
  );
}
