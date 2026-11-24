import { Link } from "react-router-dom";

import type { Pipeline as PipelineData } from "../api/pipeline";
import { describeRun } from "../api/runs";
import { ErrorNotice, ExampleTag, InfoNotice, SuccessNotice } from "../components/Notice";
import { usePipeline, useRunSearch } from "../hooks/usePipeline";

const lastRunFormat = new Intl.DateTimeFormat("en-NZ", { dateStyle: "medium", timeStyle: "short" });

type SourceRow = PipelineData["last_sources"][number];

function sourceResult(row: SourceRow): { text: string; className: string } {
  if (row.status === "not_connected") return { text: "Not connected", className: "text-muted" };
  if (row.status === "error") return { text: row.detail ?? "Failed", className: "text-bad" };
  const jobs = `${row.jobs} ${row.jobs === 1 ? "job" : "jobs"}`;
  const text = row.detail ? (row.jobs ? `${jobs} · ${row.detail}` : row.detail) : jobs;
  return { text, className: "text-ok" };
}

function SourcesCard({ rows }: { rows: SourceRow[] }) {
  return (
    <section aria-label="Where the last search looked" className="card flex flex-col gap-2">
      <h2 className="m-0 font-display text-lg font-bold">Where the last search looked</h2>
      {rows.map((row) => {
        const result = sourceResult(row);
        return (
          <div
            key={row.source}
            className="flex flex-wrap justify-between gap-x-4 gap-y-1 border-t border-line pt-2 text-sm"
          >
            <span className="font-semibold">{row.source}</span>
            <span className={result.className}>{result.text}</span>
          </div>
        );
      })}
    </section>
  );
}

export default function Pipeline() {
  const { data, error, isPending } = usePipeline();
  const run = useRunSearch();

  if (isPending) return <p className="text-muted">Loading your pipeline…</p>;
  if (error) return <ErrorNotice message={error.message} />;

  const stats = [
    { label: "Found today", value: data.stats.found_today, note: "new jobs scored" },
    { label: "Shortlisted", value: data.stats.shortlisted, note: "waiting for your decision" },
    { label: "Ready to send", value: data.stats.ready_to_send, note: "waiting for your review" },
    { label: "Replies", value: data.stats.replies_this_week, note: "this week" },
  ];
  const hasExamples = data.columns.some((column) => column.cards.some((card) => card.is_example));
  const outcome = run.data ? describeRun(run.data) : {};
  const problem = run.error?.message ?? outcome.problem;

  return (
    <>
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            {hasExamples && <ExampleTag />}
            <span className="text-[13px] text-muted">
              {data.last_run_at
                ? `Last search ran ${lastRunFormat.format(new Date(data.last_run_at))}`
                : "No search has run yet"}
            </span>
          </div>
          <h1 className="m-0 font-display text-[28px] font-extrabold tracking-tight">Pipeline</h1>
          <p className="m-0 text-muted">Every job matched to your resume, from found to replied.</p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          disabled={run.isPending}
          onClick={() => run.mutate()}
        >
          {run.isPending ? "Searching…" : "Run search now"}
        </button>
      </header>

      {outcome.summary && <SuccessNotice message={outcome.summary} />}
      {outcome.info && (
        <InfoNotice message={outcome.info}>
          <Link to="/employers" className="text-brand-dark">
            Find nearby employers
          </Link>
          <Link to="/profile" className="text-brand-dark">
            Add a careers board
          </Link>
        </InfoNotice>
      )}
      {problem && <ErrorNotice message={problem} />}

      <div className="grid grid-cols-[repeat(auto-fit,minmax(180px,1fr))] gap-3.5">
        {stats.map((stat) => (
          <div key={stat.label} className="card flex flex-col gap-1">
            <span className="text-[13px] font-medium text-muted">{stat.label}</span>
            <span className="font-display text-3xl font-extrabold">{stat.value}</span>
            <span className="text-xs text-muted">{stat.note}</span>
          </div>
        ))}
      </div>

      {data.last_sources.length > 0 && <SourcesCard rows={data.last_sources} />}

      <h2 className="m-0 font-display text-lg font-bold">Board</h2>
      <div className="overflow-x-auto pb-1.5">
        <div className="grid grid-cols-[repeat(5,minmax(200px,1fr))] gap-3">
          {data.columns.map((column) => (
            <section
              key={column.key}
              aria-label={column.name}
              className="flex flex-col gap-2.5 rounded-xl bg-column p-3"
            >
              <div className="flex justify-between text-xs font-bold tracking-wider text-muted uppercase">
                <span>{column.name}</span>
                <span>{column.count}</span>
              </div>
              {column.cards.map((card) => (
                <article
                  key={card.id}
                  className="flex flex-col gap-1.5 rounded-[10px] border border-line bg-white p-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <Link
                      to={`/jobs/${card.id}`}
                      className="text-sm font-bold text-ink hover:text-brand-dark"
                    >
                      {card.title}
                    </Link>
                    {card.score !== null && (
                      <span className="rounded-md bg-brand-soft px-1.5 py-0.5 text-xs font-bold text-brand-dark">
                        {card.score}
                      </span>
                    )}
                  </div>
                  <span className="text-[13px] text-muted">
                    {card.company} · {card.city}
                  </span>
                  <span className="text-xs text-muted">{card.meta}</span>
                  <span className="text-[11px] font-semibold text-slate">{card.source}</span>
                </article>
              ))}
            </section>
          ))}
        </div>
      </div>
    </>
  );
}
