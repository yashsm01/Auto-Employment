import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { type ContactRow, findContacts, getOutboxContacts } from "../api/outbox";
import { ErrorNotice } from "./Notice";

const checkedFormat = new Intl.DateTimeFormat("en-NZ", {
  dateStyle: "medium",
  timeStyle: "short",
  timeZone: "Pacific/Auckland",
});

const PHONE_SOURCES: Record<string, string> = {
  "Google Maps": "From Google Maps",
  Website: "From their website",
  "Job advert": "From the advert",
};

/** The plain-words label for where a phone number came from. Unknown sources show as they are. */
export function phoneSourceLabel(source: string): string {
  return PHONE_SOURCES[source] ?? source;
}

function SourceTag({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-md bg-column px-1.5 py-0.5 text-[11px] font-semibold text-slate">
      {children}
    </span>
  );
}

function EmailLine({ label, emails }: { label: string; emails: string[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
      <span className="font-semibold">{label}</span>
      {emails.map((email) => (
        <span key={email}>{email}</span>
      ))}
    </div>
  );
}

function ContactCard({ row }: { row: ContactRow }) {
  const client = useQueryClient();
  const hiringEmails = row.hiring_emails ?? [];
  const emails = row.emails ?? [];
  const find = useMutation({
    mutationFn: () => findContacts(row.application_id),
    onSuccess: (updated) =>
      client.setQueryData<{ rows: ContactRow[] }>(["outbox-contacts"], (current) =>
        current
          ? {
              rows: current.rows.map((item) =>
                item.application_id === updated.application_id ? updated : item,
              ),
            }
          : current,
      ),
  });
  const advert = row.advert_contact;

  return (
    <article aria-label={`${row.title} at ${row.company}`} className="card flex flex-col gap-2 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 flex-col">
          <b>{row.title}</b>
          <span className="text-muted">{row.company}</span>
        </div>
        {row.kind === "speculative" && (
          <span className="rounded-full bg-warn-soft px-2.5 py-0.5 text-xs font-semibold text-warn">
            Speculative
          </span>
        )}
      </div>

      {hiringEmails.length > 0 && <EmailLine label="Hiring emails" emails={hiringEmails} />}
      {emails.length > 0 && <EmailLine label="Emails" emails={emails} />}

      {advert && (
        <div className="flex flex-col gap-0.5">
          <span className="font-semibold">From the advert</span>
          {advert.name && <span>{advert.name}</span>}
          {advert.role && <span className="text-muted">{advert.role}</span>}
          {advert.email && <span>{advert.email}</span>}
          {advert.phone && <span>{advert.phone}</span>}
        </div>
      )}

      {row.phone && (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-semibold">Phone</span>
          <span>{row.phone}</span>
          {row.phone_source && <SourceTag>{phoneSourceLabel(row.phone_source)}</SourceTag>}
        </div>
      )}

      {row.address_used && <p className="m-0">Address used: {row.address_used}</p>}
      {row.missing_reason && <p className="m-0 text-warn">{row.missing_reason}</p>}
      {row.checked_at && (
        <p className="m-0 text-[13px] text-muted">
          Checked {checkedFormat.format(new Date(row.checked_at))}
        </p>
      )}

      <div>
        <button
          type="button"
          className="btn"
          aria-label={`Find contacts for ${row.company}`}
          disabled={find.isPending}
          onClick={() => find.mutate(undefined)}
        >
          {find.isPending ? "Finding contacts…" : "Find contacts"}
        </button>
      </div>
      {find.error && <ErrorNotice message={find.error.message} />}
    </article>
  );
}

export default function OutboxContacts() {
  const { data, error, isPending } = useQuery({
    queryKey: ["outbox-contacts"],
    queryFn: getOutboxContacts,
  });
  if (isPending) return null;
  if (error) return <ErrorNotice message={error.message} />;
  if (data.rows.length === 0) return null;

  return (
    <section aria-label="Contacts" className="flex flex-col gap-3">
      <h2 className="m-0 font-display text-lg font-bold">Contacts</h2>
      <p className="m-0 text-[13px] text-muted">
        The contact details each employer publishes, and why no address was found when one is
        missing.
      </p>
      {data.rows.map((row) => (
        <ContactCard key={row.application_id} row={row} />
      ))}
    </section>
  );
}
