import { useState, type FormEvent } from "react";

import type { NearbyEmployer } from "../api/employers";
import EmployerContacts, { OpeningHours, RatingLine, webUrl } from "../components/EmployerContacts";
import { ErrorNotice } from "../components/Notice";
import {
  useEmployerSearch,
  useRefreshContacts,
  useRemoveEmployer,
  useSaveEmployer,
  useSavedEmployers,
} from "../hooks/useEmployers";

const checkedFormat = new Intl.DateTimeFormat("en-NZ", { dateStyle: "medium", timeStyle: "short" });

function ResultCard({
  place,
  saved,
  busy,
  onSave,
}: {
  place: NearbyEmployer;
  saved: boolean;
  busy: boolean;
  onSave: () => void;
}) {
  const website = webUrl(place.website);
  const mapUrl = webUrl(place.map_url);
  return (
    <article className="card flex flex-wrap items-center justify-between gap-3">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="m-0 text-base font-bold">{place.name}</h3>
          <span className="rounded-full bg-column px-2.5 py-0.5 text-xs font-semibold text-slate">
            Google Maps
          </span>
        </div>
        {place.address && <span className="text-sm text-muted">{place.address}</span>}
        {place.phone && <span className="text-sm text-muted">{place.phone}</span>}
        {place.business_type && <span className="text-sm text-muted">{place.business_type}</span>}
        {place.rating != null && <RatingLine rating={place.rating} count={place.rating_count} />}
        {place.hours && place.hours.length > 0 && <OpeningHours hours={place.hours} />}
        <div className="flex flex-wrap gap-4 text-sm font-semibold">
          {mapUrl && (
            <a className="text-brand-dark" href={mapUrl} target="_blank" rel="noopener noreferrer">
              Open map
            </a>
          )}
          {website && (
            <a className="text-brand-dark" href={website} target="_blank" rel="noopener noreferrer">
              Website
            </a>
          )}
        </div>
      </div>
      {saved ? (
        <button type="button" className="btn" disabled>
          Saved
        </button>
      ) : (
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy}
          aria-label={`Save ${place.name}`}
          onClick={onSave}
        >
          Save
        </button>
      )}
    </article>
  );
}

export default function Employers() {
  const savedList = useSavedEmployers();
  const search = useEmployerSearch();
  const saveMutation = useSaveEmployer();
  const removeMutation = useRemoveEmployer();
  const refreshMutation = useRefreshContacts();
  const [business, setBusiness] = useState("");
  const [town, setTown] = useState("");
  const [savedNow, setSavedNow] = useState<Set<string>>(new Set());
  // The saved list does not carry the notes of a lookup, so the page keeps them from the lookup result.
  const [lookupNotes, setLookupNotes] = useState<Record<string, string[]>>({});
  // Each card's lookup is tracked by id, so overlapping lookups each keep their own busy state and notes.
  const [refreshing, setRefreshing] = useState<Set<string>>(new Set());
  const [lookupError, setLookupError] = useState<Error | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (business.trim() && town.trim()) {
      search.mutate({ business: business.trim(), town: town.trim() });
    }
  };

  const save = (place: NearbyEmployer) =>
    saveMutation.mutate(place, {
      onSuccess: () => setSavedNow((current) => new Set(current).add(place.place_id)),
    });

  const lookUp = (id: string) => {
    setLookupError(null);
    setRefreshing((current) => new Set(current).add(id));
    refreshMutation
      .mutateAsync(id)
      .then((contacts) =>
        setLookupNotes((current) => ({ ...current, [id]: contacts.notes ?? [] })),
      )
      .catch((error: Error) => setLookupError(error))
      .finally(() =>
        setRefreshing((current) => {
          const next = new Set(current);
          next.delete(id);
          return next;
        }),
      );
  };

  const problem =
    search.error ?? saveMutation.error ?? lookupError ?? removeMutation.error ?? savedList.error;

  return (
    <>
      <header className="flex flex-col gap-1.5">
        <h1 className="m-0 font-display text-[28px] font-extrabold tracking-tight">
          Nearby employers
        </h1>
        <p className="m-0 max-w-3xl text-muted">
          Google Maps lists businesses, not jobs. Saved employers have their websites checked for
          open jobs on every search. Searches also add employers for your towns automatically.
        </p>
      </header>

      {problem && <ErrorNotice message={problem.message} />}

      <form className="card flex flex-wrap items-end gap-3" onSubmit={submit}>
        <div className="flex min-w-48 flex-1 flex-col gap-1.5">
          <label className="label" htmlFor="business">
            Type of business
          </label>
          <input
            id="business"
            className="input"
            placeholder="e.g. software company"
            value={business}
            onChange={(event) => setBusiness(event.target.value)}
          />
        </div>
        <div className="flex min-w-48 flex-1 flex-col gap-1.5">
          <label className="label" htmlFor="town">
            Town or region
          </label>
          <input
            id="town"
            className="input"
            placeholder="e.g. Timaru"
            value={town}
            onChange={(event) => setTown(event.target.value)}
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={search.isPending}>
          {search.isPending ? "Searching…" : "Search Google Maps"}
        </button>
      </form>

      {search.data && (
        <section aria-label="Search results" className="flex flex-col gap-3">
          <span className="text-[13px] text-muted">
            {search.data.results.length} found · {search.data.searches_left} searches left today
          </span>
          {search.data.results.length === 0 && (
            <p className="card m-0 text-muted">No businesses found. Try a broader search.</p>
          )}
          {search.data.results.map((place) => (
            <ResultCard
              key={place.place_id}
              place={place}
              saved={place.saved || savedNow.has(place.place_id)}
              busy={saveMutation.isPending && saveMutation.variables?.place_id === place.place_id}
              onSave={() => save(place)}
            />
          ))}
        </section>
      )}

      <section aria-label="Employers checked on each search" className="card flex flex-col gap-2">
        <h2 className="m-0 font-display text-[17px] font-bold">Employers checked on each search</h2>
        {savedList.data?.items.length === 0 && (
          <p className="m-0 text-sm text-muted">
            No employers saved yet. Search above, or run a job search to add some automatically.
          </p>
        )}
        {savedList.data?.items.map((employer) => {
          const website = webUrl(employer.website);
          const mapUrl = webUrl(employer.map_url);
          return (
          <div
            key={employer.id}
            className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-2"
          >
            <div className="flex min-w-0 flex-col gap-0.5 text-sm">
              <b>{employer.name}</b>
              <span className="text-muted">
                {employer.last_checked
                  ? `Website checked ${checkedFormat.format(new Date(employer.last_checked))}`
                  : "Website not checked yet"}
                {employer.address ? ` · ${employer.address}` : ""}
              </span>
              <div className="flex flex-wrap gap-4 font-semibold">
                {mapUrl && (
                  <a className="text-brand-dark" href={mapUrl} target="_blank" rel="noopener noreferrer">
                    Map
                  </a>
                )}
                {website && (
                  <a className="text-brand-dark" href={website} target="_blank" rel="noopener noreferrer">
                    Website
                  </a>
                )}
              </div>
              <div className="mt-1">
                <EmployerContacts
                  contacts={{
                    ...employer.contacts,
                    notes: lookupNotes[employer.id] ?? employer.contacts?.notes ?? [],
                  }}
                  onRefresh={() => lookUp(employer.id)}
                  busy={refreshing.has(employer.id)}
                />
              </div>
            </div>
            <button
              type="button"
              className="btn"
              disabled={removeMutation.isPending}
              aria-label={`Remove ${employer.name}`}
              onClick={() => removeMutation.mutate(employer.id)}
            >
              Remove
            </button>
          </div>
          );
        })}
      </section>
    </>
  );
}
