import { type ReactNode, useState } from "react";
import { Link } from "react-router-dom";

import { apiUrl } from "../api/client";
import {
  cancelEmail,
  markApplied,
  type Outcome,
  type OutboxItem,
  queueEmail,
  recordOutcome,
  retryEmail,
  saveDailyLimit,
  type ToSendItem,
  type WaitingItem,
} from "../api/outbox";
import { ErrorNotice, InfoNotice } from "../components/Notice";
import { useOutbox, useOutboxAction } from "../hooks/useOutbox";

const dateFormat = new Intl.DateTimeFormat("en-NZ", { dateStyle: "medium" });
const timeFormat = new Intl.DateTimeFormat("en-NZ", { dateStyle: "medium", timeStyle: "short" });

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="flex flex-col gap-3">
      <h2 className="m-0 font-display text-lg font-bold">{title}</h2>
      {children}
    </section>
  );
}

function JobHeading({ title, company, id }: { title: string; company: string; id: string }) {
  return (
    <div className="flex min-w-0 flex-col">
      <Link to={`/jobs/${id}`} className="font-bold text-ink no-underline hover:underline">
        {title}
      </Link>
      <span className="text-sm text-muted">{company}</span>
    </div>
  );
}

function ReadyItem({ item }: { item: ToSendItem }) {
  const [to, setTo] = useState(item.suggested_to ?? "");
  const queue = useOutboxAction((address: string) => queueEmail(item.application_id, address));
  const applied = useOutboxAction(() => markApplied(item.application_id));
  const inputId = `send-to-${item.application_id}`;
  const busy = queue.isPending || applied.isPending;

  return (
    <article aria-label={`${item.title} at ${item.company}`} className="card flex flex-col gap-3">
      <JobHeading title={item.title} company={item.company} id={item.application_id} />
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex min-w-[240px] flex-1 flex-col gap-1.5">
          <label className="label" htmlFor={inputId}>
            Send to
          </label>
          <input
            id={inputId}
            className="input"
            type="email"
            value={to}
            placeholder="jobs@company.co.nz"
            onChange={(event) => setTo(event.target.value)}
          />
        </div>
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy || !to.trim()}
          onClick={() => queue.mutate(to.trim())}
        >
          Queue email
        </button>
        <button type="button" className="btn" disabled={busy} onClick={() => applied.mutate()}>
          I applied on the job site
        </button>
      </div>
      {!item.suggested_to && (
        <p className="m-0 text-[13px] text-muted">
          The advert has no email address. Apply on the job site with the PDF and cover note,
          then press "I applied on the job site", or type an address you found.
        </p>
      )}
      <div className="flex flex-wrap gap-4 text-sm font-semibold">
        {item.job_url && (
          <a className="text-brand-dark" href={item.job_url} target="_blank" rel="noopener noreferrer">
            View job post
          </a>
        )}
        {item.pdf_url && (
          <a className="text-brand-dark" href={apiUrl(item.pdf_url)} target="_blank" rel="noopener noreferrer">
            Download PDF
          </a>
        )}
        <Link className="text-brand-dark" to={`/jobs/${item.application_id}/resume`}>
          Edit cover note
        </Link>
      </div>
      <details className="text-sm">
        <summary className="cursor-pointer text-muted">Cover note</summary>
        <p className="m-0 mt-2 whitespace-pre-line">{item.cover_note}</p>
      </details>
      {(queue.error ?? applied.error) && (
        <ErrorNotice message={(queue.error ?? applied.error)!.message} />
      )}
    </article>
  );
}

function EmailItem({ item, failed }: { item: OutboxItem; failed: boolean }) {
  const cancel = useOutboxAction(() => cancelEmail(item.id));
  const retry = useOutboxAction(() => retryEmail(item.id));
  return (
    <article aria-label={`${item.subject} to ${item.to}`} className="card flex flex-col gap-2">
      <JobHeading title={item.title} company={item.company} id={item.application_id} />
      <span className="text-sm">
        {item.kind === "follow_up" ? "Follow-up" : "Application"} to <b>{item.to}</b> ·{" "}
        {item.subject}
      </span>
      {!failed && (
        <span className="text-[13px] text-muted">
          {item.attempts > 0
            ? `Retrying after ${item.attempts} failed ${item.attempts === 1 ? "try" : "tries"}: ${item.error}`
            : `Waiting since ${timeFormat.format(new Date(item.scheduled_at))}`}
        </span>
      )}
      {failed && <span className="text-sm text-bad">{item.error}</span>}
      <div className="flex flex-wrap gap-2.5">
        {failed && (
          <button type="button" className="btn" disabled={retry.isPending} onClick={() => retry.mutate(undefined)}>
            Try again
          </button>
        )}
        <button type="button" className="btn" disabled={cancel.isPending} onClick={() => cancel.mutate(undefined)}>
          Cancel
        </button>
      </div>
      {(cancel.error ?? retry.error) && (
        <ErrorNotice message={(cancel.error ?? retry.error)!.message} />
      )}
    </article>
  );
}

function WaitingRow({ item }: { item: WaitingItem }) {
  const outcome = useOutboxAction((action: Outcome) => recordOutcome(item.application_id, action));
  const applied = item.applied_at ? dateFormat.format(new Date(item.applied_at)) : "";
  return (
    <article aria-label={`${item.title} at ${item.company}`} className="card flex flex-col gap-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <JobHeading title={item.title} company={item.company} id={item.application_id} />
        {item.follow_up_due && (
          <span className="rounded-full bg-warn-soft px-2.5 py-0.5 text-xs font-semibold text-warn">
            Follow-up due
          </span>
        )}
      </div>
      <span className="text-sm">
        {item.apply_method === "email"
          ? `Emailed to ${item.to} on ${applied}`
          : `Applied on the job site on ${applied}`}
        {item.follow_ups > 0 && ` · ${item.follow_ups} follow-up${item.follow_ups > 1 ? "s" : ""}`}
      </span>
      {item.next_follow_up && !item.follow_up_due && (
        <span className="text-[13px] text-muted">
          {item.apply_method === "email" ? "Follow-up email on" : "Follow-up reminder on"}{" "}
          {dateFormat.format(new Date(item.next_follow_up))}
        </span>
      )}
      <div className="flex flex-wrap gap-2.5">
        {item.apply_method === "manual" && item.follow_up_due && (
          <button type="button" className="btn btn-primary" disabled={outcome.isPending}
                  onClick={() => outcome.mutate("followed_up")}>
            I followed up
          </button>
        )}
        <button type="button" className="btn" disabled={outcome.isPending}
                onClick={() => outcome.mutate("replied")}>
          They replied
        </button>
        {item.next_follow_up && (
          <button type="button" className="btn" disabled={outcome.isPending}
                  onClick={() => outcome.mutate("stop_follow_ups")}>
            Stop follow-ups
          </button>
        )}
        <button type="button" className="btn" disabled={outcome.isPending}
                onClick={() => outcome.mutate("closed")}>
          Close
        </button>
      </div>
      {outcome.error && <ErrorNotice message={outcome.error.message} />}
    </article>
  );
}

function DailyLimit({ limit, sent }: { limit: number; sent: number }) {
  const [value, setValue] = useState(String(limit));
  const save = useOutboxAction((next: number) => saveDailyLimit(next));
  const parsed = Number.parseInt(value, 10);
  const valid = Number.isInteger(parsed) && parsed >= 0 && parsed <= 50;
  return (
    <div className="flex flex-wrap items-end gap-3">
      <p className="m-0 text-sm">
        {sent} of {limit} emails sent today
      </p>
      <div className="flex flex-col gap-1.5">
        <label className="label" htmlFor="daily-limit">
          Daily limit
        </label>
        <input id="daily-limit" className="input max-w-24" type="number" min={0} max={50}
               value={value} onChange={(event) => setValue(event.target.value)} />
      </div>
      <button type="button" className="btn" disabled={!valid || save.isPending}
              onClick={() => save.mutate(parsed)}>
        Save limit
      </button>
      {save.error && <ErrorNotice message={save.error.message} />}
    </div>
  );
}

export default function Outbox() {
  const { data, error, isPending } = useOutbox();
  if (isPending) return <p className="text-muted">Loading the outbox…</p>;
  if (error) return <ErrorNotice message={error.message} />;

  const empty =
    data.to_send.length + data.queued.length + data.failed.length + data.waiting.length === 0;

  return (
    <>
      <header className="flex flex-col gap-1.5">
        <h1 className="m-0 font-display text-[28px] font-extrabold tracking-tight">
          Outbox and follow-ups
        </h1>
        <p className="m-0 max-w-3xl text-muted">
          Approved applications go out from here, at most {data.daily_limit} a day. If there's no
          reply, a polite follow-up goes 5 working days later, and the job closes after two.
        </p>
      </header>

      {!data.sending_enabled && (
        <InfoNotice message="Email sending is off. To send from your Gmail, add EMAIL_SEND_ENABLED=true to backend/.env and restart the backend. Until then, queued emails wait here." />
      )}
      {!data.reading_enabled && (
        <InfoNotice message="Replies can't be checked, because Gmail reading is not connected. Press They replied when an employer gets back to you." />
      )}
      <DailyLimit key={data.daily_limit} limit={data.daily_limit} sent={data.sent_today} />

      {empty && (
        <p className="card m-0 text-muted">
          Nothing to send yet. Approve a tailored resume on Resume review to start.
        </p>
      )}
      {data.to_send.length > 0 && (
        <Section title="Ready to apply">
          {data.to_send.map((item) => (
            <ReadyItem key={item.application_id} item={item} />
          ))}
        </Section>
      )}
      {data.queued.length > 0 && (
        <Section title="Queued">
          {data.queued.map((item) => (
            <EmailItem key={item.id} item={item} failed={false} />
          ))}
        </Section>
      )}
      {data.failed.length > 0 && (
        <Section title="Failed">
          {data.failed.map((item) => (
            <EmailItem key={item.id} item={item} failed />
          ))}
        </Section>
      )}
      {data.waiting.length > 0 && (
        <Section title="Waiting for a reply">
          {data.waiting.map((item) => (
            <WaitingRow key={item.application_id} item={item} />
          ))}
        </Section>
      )}
      {data.replied.length > 0 && (
        <Section title="Replied">
          <ul className="m-0 flex flex-col gap-1.5 pl-5 text-sm">
            {data.replied.map((item) => (
              <li key={item.application_id}>
                <Link to={`/jobs/${item.application_id}`} className="text-brand-dark">
                  {item.title}
                </Link>{" "}
                · {item.company} · {dateFormat.format(new Date(item.updated_at))}
              </li>
            ))}
          </ul>
        </Section>
      )}
    </>
  );
}
