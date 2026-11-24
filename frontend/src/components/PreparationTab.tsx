import { type ReactNode, useState } from "react";

import type { PrepPack, SourceLink, SourcedLine } from "../api/prep";
import { usePrep, useRunPrep } from "../hooks/usePrep";
import { ErrorNotice, InfoNotice } from "./Notice";

const NO_KEY = "Deep search needs a Claude key in backend/.env.";
const timeFormat = new Intl.DateTimeFormat("en-NZ", { dateStyle: "medium", timeStyle: "short" });

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="card flex min-w-0 flex-col gap-2">
      <h2 className="m-0 font-display text-[17px] font-bold">{title}</h2>
      {children}
    </section>
  );
}

function Marks({ ids, sources }: { ids: string[]; sources: Map<string, SourceLink> }) {
  return (
    <>
      {ids.map((id) => {
        const url = sources.get(id)?.url;
        return url ? (
          <a
            key={id}
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-1 text-xs font-semibold text-brand-dark"
          >
            [{id}]
          </a>
        ) : (
          <span key={id} className="ml-1 text-xs text-muted">
            [{id}]
          </span>
        );
      })}
    </>
  );
}

function Lines({ lines, sources }: { lines: SourcedLine[]; sources: Map<string, SourceLink> }) {
  if (lines.length === 0) return <p className="m-0 text-sm text-muted">Nothing found.</p>;
  return (
    <ul className="m-0 flex flex-col gap-1.5 pl-5 text-sm">
      {lines.map((line, index) => (
        <li key={`${index}-${line.text}`}>
          {line.text}
          <Marks ids={line.source_ids ?? []} sources={sources} />
          {line.quote && (
            <span className="block text-xs text-muted">“{line.quote}”</span>
          )}
        </li>
      ))}
    </ul>
  );
}

function Items({ items }: { items: string[] }) {
  if (items.length === 0) return <p className="m-0 text-sm text-muted">None.</p>;
  return (
    <ul className="m-0 flex flex-col gap-1.5 pl-5 text-sm">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function Pack({ pack, sources }: { pack: PrepPack; sources: SourceLink[] }) {
  const byId = new Map(sources.map((source) => [source.id, source]));
  const evidence = pack.evidence ?? [];
  const couldNotVerify = pack.could_not_verify ?? [];
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,320px),1fr))] gap-4">
      <Section title="Your evidence for each requirement">
        <ul className="m-0 flex list-none flex-col gap-2 p-0 text-sm">
          {evidence.map((item) => (
            <li key={item.requirement} className="flex flex-col gap-0.5">
              <b>{item.requirement}</b>
              {item.status === "matched" && <span>{item.evidence}</span>}
              {item.status === "gap" && <span className="text-bad">Gap: not shown in your resume</span>}
              {item.status === "check" && (
                <span className="text-warn">
                  Check this: “{item.evidence}” is not word for word in your resume
                </span>
              )}
            </li>
          ))}
        </ul>
      </Section>
      <Section title="Likely interview stages (unconfirmed)">
        <Items items={pack.interview_stages ?? []} />
        <p className="m-0 text-[13px] text-muted">Confirm these with the recruiter.</p>
      </Section>
      <Section title="Pay range">
        {pack.pay ? (
          <p className="m-0 text-sm">
            {pack.pay.text}
            <Marks ids={pack.pay.source_ids ?? []} sources={byId} />
          </p>
        ) : (
          <p className="m-0 text-sm text-muted">Unknown. No source gave a pay range.</p>
        )}
      </Section>
      <Section title="About the employer">
        <Lines lines={pack.employer ?? []} sources={byId} />
      </Section>
      <Section title="Questions to ask">
        <Items items={pack.questions ?? []} />
      </Section>
      <Section title="Things to brush up on">
        <Items items={pack.brush_up ?? []} />
      </Section>
      <Section title="Practical details">
        <Lines lines={pack.practical ?? []} sources={byId} />
        {pack.directions_url && (
          <a
            className="text-sm font-semibold text-brand-dark"
            href={pack.directions_url}
            target="_blank"
            rel="noopener noreferrer"
          >
            Directions on Google Maps
          </a>
        )}
      </Section>
      <Section title="Application tips">
        <Items items={pack.tips ?? []} />
      </Section>
      <Section title="Unknowns">
        <Items items={pack.unknowns ?? []} />
      </Section>
      {couldNotVerify.length > 0 && (
        <Section title="Could not verify">
          <p className="m-0 text-[13px] text-muted">
            The AI noted these, but the words could not be found on the page they came from,
            so they were left out of the pack.
          </p>
          <Items items={couldNotVerify} />
        </Section>
      )}
    </div>
  );
}

export default function PreparationTab({ applicationId }: { applicationId: string }) {
  const { data: view, error, isPending } = usePrep(applicationId);
  const run = useRunPrep(applicationId);
  const [extra, setExtra] = useState("");

  if (isPending) return <p className="text-muted">Loading preparation…</p>;
  if (error) return <ErrorNotice message={error.message} />;

  const busy = view.status === "queued" || view.status === "running";
  const start = () => run.mutate(extra.trim() || null);

  return (
    <div className="flex flex-col gap-4">
      {!view.available && <InfoNotice message={NO_KEY} />}
      {view.status === "failed" && view.error && <ErrorNotice message={view.error} />}
      {run.error && <ErrorNotice message={run.error.message} />}
      {busy && <InfoNotice message="Deep search is running. This takes about a minute." />}

      {view.available && !busy && (
        <section className="card flex flex-col gap-3">
          <label className="label" htmlFor="prep-extra">
            Extra details (a link or text)
          </label>
          <textarea
            id="prep-extra"
            className="input min-h-24 py-2"
            value={extra}
            onChange={(event) => setExtra(event.target.value)}
            placeholder="A company page or news link, or text from the advert"
          />
          <p className="m-0 text-[13px] text-muted">
            Links on SEEK, LinkedIn, Indeed, Glassdoor or Trade Me can't be opened. Paste the
            text instead.
          </p>
          <button
            type="button"
            className="btn btn-primary self-start"
            disabled={run.isPending}
            onClick={start}
          >
            {view.status === "failed" ? "Try again" : "Run deep search"}
          </button>
        </section>
      )}

      {view.status === "done" && view.pack && (
        <>
          <Pack pack={view.pack} sources={view.sources ?? []} />
          <Section title="Sources">
            <ul className="m-0 flex flex-col gap-1 pl-5 text-sm">
              {(view.sources ?? []).map((source) => (
                <li key={source.id}>
                  [{source.id}]{" "}
                  {source.url ? (
                    <a href={source.url} target="_blank" rel="noopener noreferrer"
                       className="text-brand-dark">
                      {source.title}
                    </a>
                  ) : (
                    source.title
                  )}
                </li>
              ))}
            </ul>
            {(view.notes ?? []).length > 0 && (
              <ul className="m-0 flex flex-col gap-1 pl-5 text-[13px] text-muted">
                {(view.notes ?? []).map((note) => (
                  <li key={note}>{note}</li>
                ))}
              </ul>
            )}
          </Section>
        </>
      )}

      <p className="m-0 text-[13px] text-muted">
        {view.status === "done" && view.cost_nzd !== null && view.cost_nzd !== undefined
          ? `This run cost NZ$${view.cost_nzd.toFixed(2)}${
              view.finished_at ? ` · ${timeFormat.format(new Date(view.finished_at))}` : ""
            } · `
          : ""}
        {view.used_this_month} of {view.monthly_limit} deep searches used this month
      </p>
    </div>
  );
}
