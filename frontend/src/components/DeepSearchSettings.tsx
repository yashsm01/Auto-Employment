import { useState } from "react";

import type { DeepSearchView } from "../api/prep";
import { useDeepSearch, useSaveDeepSearch } from "../hooks/usePrep";
import { ErrorNotice, InfoNotice } from "./Notice";

function Form({ value }: { value: DeepSearchView }) {
  const [enabled, setEnabled] = useState(value.enabled ?? false);
  const [limit, setLimit] = useState(String(value.monthly_limit ?? 30));
  const save = useSaveDeepSearch();
  const parsed = Number.parseInt(limit, 10);
  const valid = Number.isInteger(parsed) && parsed >= 0 && parsed <= 500;

  return (
    <section className="card flex flex-col gap-3">
      <h2 className="m-0 font-display text-[17px] font-bold">Deep search</h2>
      <p className="m-0 text-[13px] text-muted">
        For one job, researches the employer and the role and writes a preparation pack with
        sources. About NZ$0.07–0.15 per job. When switched on, it runs each time you approve a
        job; you can also run it from any job page.
      </p>
      {!value.available && (
        <InfoNotice message="Deep search needs a Claude key in backend/.env." />
      )}
      <label className="flex min-h-9 items-center gap-2 text-sm font-semibold">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
        />
        Deep search
      </label>
      <div className="flex flex-col gap-1.5">
        <label className="label" htmlFor="deep-search-limit">
          Monthly limit
        </label>
        <input
          id="deep-search-limit"
          className="input max-w-32"
          type="number"
          min={0}
          max={500}
          value={limit}
          onChange={(event) => setLimit(event.target.value)}
        />
      </div>
      <p className="m-0 text-sm">
        {value.used_this_month} of {value.monthly_limit} deep searches used this month
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="btn self-start"
          disabled={save.isPending || !valid}
          onClick={() => save.mutate({ enabled, monthly_limit: parsed })}
        >
          Save deep search settings
        </button>
        {save.isSuccess && <span className="text-sm text-ok">Deep search settings saved.</span>}
      </div>
      {save.error && <ErrorNotice message={save.error.message} />}
    </section>
  );
}

export default function DeepSearchSettings() {
  const { data, error, isPending } = useDeepSearch();
  if (isPending) return null;
  if (error) return <ErrorNotice message={error.message} />;
  return <Form value={data} />;
}
