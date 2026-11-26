import type { ReactNode } from "react";

import type { components } from "../types/api";

type Contacts = components["schemas"]["EmployerContacts"];

const checkedFormat = new Intl.DateTimeFormat("en-NZ", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "Pacific/Auckland",
});

/** Returns the address only when it is an http(s) link, so other schemes never become links. */
export function webUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const { protocol } = new URL(value);
    return protocol === "http:" || protocol === "https:" ? value : null;
  } catch {
    return null;
  }
}

export function SourceBadge({ children }: { children: ReactNode }) {
  return (
    <span className="rounded-md bg-column px-1.5 py-0.5 text-[11px] font-semibold text-slate">
      {children}
    </span>
  );
}

function ExternalLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a className="text-brand-dark" href={href} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}

/** The rating, such as "★ 4.6 (120)". `source` is an optional label, such as a badge. */
export function RatingLine({
  rating,
  count,
  source,
}: {
  rating: number;
  count?: number | null;
  source?: ReactNode;
}) {
  const text = `★ ${rating.toFixed(1)}${count != null ? ` (${count})` : ""}`;
  return (
    <span className="flex flex-wrap items-center gap-1.5 text-sm">
      <span>{text}</span>
      {source}
    </span>
  );
}

/** Opening hours, folded away until someone asks for them. `source` is an optional label. */
export function OpeningHours({ hours, source }: { hours: string[]; source?: ReactNode }) {
  return (
    <details className="text-sm">
      <summary className="flex cursor-pointer flex-wrap items-center gap-1.5 font-semibold">
        <span>Opening hours</span>
        {source}
      </summary>
      <ul className="m-0 mt-1 flex list-none flex-col gap-0.5 p-0 text-muted">
        {hours.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </details>
  );
}

function Line({ children }: { children: ReactNode }) {
  return <div className="flex flex-wrap items-center gap-x-2 gap-y-1">{children}</div>;
}

export default function EmployerContacts({
  contacts,
  onRefresh,
  busy = false,
}: {
  contacts: Contacts;
  onRefresh?: () => void;
  busy?: boolean;
}) {
  const website = webUrl(contacts.website);
  const contactPage = webUrl(contacts.contact_page);
  const careersPage = webUrl(contacts.careers_page);
  const linkedin = webUrl(contacts.linkedin);
  const emails = contacts.emails ?? [];
  const hiringEmails = contacts.hiring_emails ?? [];
  const recruiters = contacts.recruiters ?? [];
  const hours = contacts.hours ?? [];
  const notes = contacts.notes ?? [];
  const hasContact =
    Boolean(contacts.phone) ||
    emails.length > 0 ||
    hiringEmails.length > 0 ||
    recruiters.length > 0 ||
    Boolean(contactPage || careersPage || linkedin);

  return (
    <div className="flex flex-col gap-2 text-sm">
      {onRefresh && (
        <Line>
          <button type="button" className="btn" disabled={busy} onClick={onRefresh}>
            Get contact details
          </button>
          {busy && <span className="text-muted">Checking the website. This can take a few seconds.</span>}
        </Line>
      )}

      {!hasContact && <p className="m-0 text-muted">No contact details found yet.</p>}

      {contacts.phone && (
        <Line>
          <a className="text-brand-dark" href={`tel:${contacts.phone.replace(/[\s-]/g, "")}`}>
            {contacts.phone}
          </a>
          {contacts.phone_source && <SourceBadge>{contacts.phone_source}</SourceBadge>}
        </Line>
      )}

      {emails.map((email) => (
        <Line key={`email:${email}`}>
          <a className="text-brand-dark" href={`mailto:${email}`}>
            {email}
          </a>
          <SourceBadge>Website</SourceBadge>
        </Line>
      ))}

      {hiringEmails.map((email) => (
        <Line key={`hiring:${email}`}>
          <SourceBadge>Hiring</SourceBadge>
          <a className="text-brand-dark" href={`mailto:${email}`}>
            {email}
          </a>
          <SourceBadge>Website</SourceBadge>
        </Line>
      ))}

      {recruiters.map((person) => {
        const recruiterSource = webUrl(person.source_url);
        return (
          <Line key={`recruiter:${person.name}:${person.role}`}>
            <SourceBadge>Hiring</SourceBadge>
            <span className="font-semibold">{person.name}</span>
            <span className="text-muted">{person.role}</span>
            {person.email && (
              <a className="text-brand-dark" href={`mailto:${person.email}`}>
                {person.email}
              </a>
            )}
            {person.phone && (
              <a className="text-brand-dark" href={`tel:${person.phone.replace(/[\s-]/g, "")}`}>
                {person.phone}
              </a>
            )}
            {recruiterSource && <ExternalLink href={recruiterSource}>Source</ExternalLink>}
            <SourceBadge>Website</SourceBadge>
          </Line>
        );
      })}

      {(website || contactPage || careersPage || linkedin) && (
        <Line>
          {website && <ExternalLink href={website}>Website</ExternalLink>}
          {contactPage && (
            <Line>
              <ExternalLink href={contactPage}>Contact page</ExternalLink>
              <SourceBadge>Website</SourceBadge>
            </Line>
          )}
          {careersPage && (
            <Line>
              <ExternalLink href={careersPage}>Careers page</ExternalLink>
              <SourceBadge>Website</SourceBadge>
            </Line>
          )}
          {linkedin && (
            <Line>
              <ExternalLink href={linkedin}>LinkedIn</ExternalLink>
              <SourceBadge>Website</SourceBadge>
            </Line>
          )}
        </Line>
      )}

      {contacts.rating != null && (
        <RatingLine
          rating={contacts.rating}
          count={contacts.rating_count}
          source={<SourceBadge>Google Maps</SourceBadge>}
        />
      )}

      {hours.length > 0 && (
        <OpeningHours hours={hours} source={<SourceBadge>Google Maps</SourceBadge>} />
      )}

      {contacts.checked_at && (
        <span className="text-[13px] text-muted">
          Checked {checkedFormat.format(new Date(contacts.checked_at))}
        </span>
      )}

      {notes.length > 0 && (
        <ul className="m-0 flex list-none flex-col gap-1 p-0 text-[13px] text-muted">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
