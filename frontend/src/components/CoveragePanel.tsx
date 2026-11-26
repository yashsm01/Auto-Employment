import type { Coverage, SkillCoverage } from "../api/resumes";

type Decision = "have" | "no" | null;

const GUIDE =
  "How many of the ad's skills your CV shows, and where. Employers' systems differ, so this is a guide, not a prediction of an interview.";

const buttonClass = "btn min-h-9 px-3 text-[13px]";

function SkillRow({
  item,
  busy,
  onDecide,
}: {
  item: SkillCoverage;
  busy: boolean;
  onDecide: (skill: string, decision: Decision) => void;
}) {
  const { name, status, evidence, matched_as } = item;
  return (
    <li className="flex flex-wrap items-start justify-between gap-3 border-t border-line pt-2.5 first:border-t-0 first:pt-0">
      <div className="flex min-w-0 flex-[1_1_240px] flex-col gap-0.5">
        <b className="text-sm">{name}</b>
        {evidence && <span className="text-[13px] text-muted">{evidence}</span>}
        {matched_as && <span className="text-[13px] text-muted">Matched as {matched_as}</span>}
      </div>
      <div className="flex flex-wrap gap-2">
        {status === "missing" && (
          <>
            <button
              type="button"
              className={buttonClass}
              disabled={busy}
              aria-label={`I have this: ${name}`}
              onClick={() => onDecide(name, "have")}
            >
              I have this
            </button>
            <button
              type="button"
              className={buttonClass}
              disabled={busy}
              aria-label={`Not me: ${name}`}
              onClick={() => onDecide(name, "no")}
            >
              Not me
            </button>
          </>
        )}
        {(status === "added" || status === "declined") && (
          <button
            type="button"
            className={buttonClass}
            disabled={busy}
            aria-label={`Undo: ${name}`}
            onClick={() => onDecide(name, null)}
          >
            Undo
          </button>
        )}
      </div>
    </li>
  );
}

function SkillGroup({
  label,
  items,
  busy,
  onDecide,
}: {
  label: string;
  items: SkillCoverage[];
  busy: boolean;
  onDecide: (skill: string, decision: Decision) => void;
}) {
  const covered = items.filter((item) => item.status === "shown" || item.status === "added").length;
  return (
    <section role="group" aria-label={`${label} (${covered} of ${items.length})`} className="flex flex-col gap-2">
      <h3 className="m-0 text-sm font-bold">
        {label} <span className="font-normal text-muted">· {covered} of {items.length} shown</span>
      </h3>
      <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
        {items.map((item) => (
          <SkillRow key={item.name} item={item} busy={busy} onDecide={onDecide} />
        ))}
      </ul>
    </section>
  );
}

export default function CoveragePanel({
  coverage,
  onDecide,
  busy = false,
}: {
  coverage: Coverage;
  onDecide: (skill: string, decision: Decision) => void;
  busy?: boolean;
}) {
  const empty = coverage.required.length === 0 && coverage.preferred.length === 0;
  return (
    <section aria-label="Skill coverage" className="card flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <h2 className="m-0 font-display text-[17px] font-bold">Skill coverage for this job</h2>
        <p className="m-0 text-[13px] text-muted">{GUIDE}</p>
      </div>
      {empty ? (
        <p className="m-0 text-sm text-muted">No skills found in this ad.</p>
      ) : coverage.split ? (
        <>
          <SkillGroup label="Required in the ad" items={coverage.required} busy={busy} onDecide={onDecide} />
          <SkillGroup label="Nice to have" items={coverage.preferred} busy={busy} onDecide={onDecide} />
        </>
      ) : (
        <SkillGroup
          label="Skills the ad mentions"
          items={[...coverage.required, ...coverage.preferred]}
          busy={busy}
          onDecide={onDecide}
        />
      )}
    </section>
  );
}
