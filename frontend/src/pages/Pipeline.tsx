import { ExampleTag, ErrorNotice, SuccessNotice } from "../components/Notice";
import type { RunResponse } from "../api/runs";
import { usePipeline, useRunSearch } from "../hooks/usePipeline";

const lastRunFormat = new Intl.DateTimeFormat("en-NZ", { dateStyle: "medium", timeStyle: "short" });

function runSummary(result: RunResponse): string {
  const { new_jobs: newJobs = 0, shortlisted = 0 } = result.output as {
    new_jobs?: number;
    shortlisted?: number;
  };
  return `Search finished: ${newJobs} new jobs, ${shortlisted} shortlisted.`;
}

function runProblem(result: RunResponse | undefined, failure: Error | null): string | null {
  if (failure) return failure.message;
  if (!result) return null;
  if (result.status === "error") return result.error ?? "The search failed.";
  const errors = (result.output.errors ?? []) as string[];
  return errors.length ? `Some sources failed: ${errors.join("; ")}` : null;
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
  const problem = runProblem(run.data, run.error);
  const finished = run.data?.status === "ok" ? run.data : undefined;

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

      {finished && <SuccessNotice message={runSummary(finished)} />}
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
                    <b className="text-sm">{card.title}</b>
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
                </article>
              ))}
            </section>
          ))}
        </div>
      </div>
    </>
  );
}
