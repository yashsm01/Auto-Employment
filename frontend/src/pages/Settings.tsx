import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import {
  type AutoModeView,
  type CallItem,
  getAutoMode,
  getPhase4,
  getWhatsAppLink,
  saveAutoMode,
  testCall,
  testWhatsApp,
  unlinkWhatsApp,
} from "../api/settings";
import { ErrorNotice, InfoNotice, SuccessNotice } from "../components/Notice";

const timeFormat = new Intl.DateTimeFormat("en-NZ", {
  dateStyle: "medium",
  timeStyle: "short",
});

function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="card flex flex-col gap-3">
      <h2 className="m-0 font-display text-[17px] font-bold">{title}</h2>
      {children}
    </section>
  );
}

function duration(seconds: number | null | undefined) {
  if (seconds === null || seconds === undefined) return "";
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`;
}

function CallRow({ call }: { call: CallItem }) {
  const who =
    call.purpose === "test"
      ? "Test call to your phone"
      : `${call.company} · ${call.title}`;
  return (
    <li className="flex flex-col gap-1 border-t border-line pt-2 text-sm">
      <span>
        <b>{who}</b> · {timeFormat.format(new Date(call.created_at))} ·{" "}
        {call.status}
        {call.duration_sec ? ` · ${duration(call.duration_sec)}` : ""}
      </span>
      {call.captured_email && <span>Email given: {call.captured_email}</span>}
      {call.error && <span className="text-bad">{call.error}</span>}
      {call.transcript && (
        <details>
          <summary className="cursor-pointer text-muted">Transcript</summary>
          <p className="m-0 mt-1 whitespace-pre-line">{call.transcript}</p>
        </details>
      )}
    </li>
  );
}

function AutoModeForm({ value }: { value: AutoModeView }) {
  const client = useQueryClient();
  const [enabled, setEnabled] = useState(value.enabled ?? false);
  const [minScore, setMinScore] = useState(String(value.min_score ?? 80));
  const [limit, setLimit] = useState(String(value.daily_limit ?? 5));
  const save = useMutation({
    mutationFn: saveAutoMode,
    onSuccess: (saved) => client.setQueryData(["auto-mode"], saved),
  });
  const score = Number.parseInt(minScore, 10);
  const perDay = Number.parseInt(limit, 10);
  const valid = score >= 0 && score <= 100 && perDay >= 0 && perDay <= 20;

  return (
    <Card title="Auto mode">
      <p className="m-0 text-sm">
        When on, the app acts for you every 15 minutes. It approves shortlisted
        jobs that score at least your minimum, up to your daily limit, best
        first. It then approves the tailored resume and queues the email when
        the advert gives an address. Jobs without an address wait in the Outbox
        for you to apply. It never approves resumes for jobs you approved
        yourself.
      </p>
      {!value.sending_enabled && (
        <InfoNotice message="Email sending is off, so auto mode will approve and tailor, but emails wait in the Outbox until you add EMAIL_SEND_ENABLED=true." />
      )}
      <label className="flex min-h-9 items-center gap-2 text-sm font-semibold">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
        />
        Auto mode
      </label>
      <div className="flex flex-wrap gap-4">
        <div className="flex flex-col gap-1.5">
          <label className="label" htmlFor="auto-min-score">
            Minimum score
          </label>
          <input
            id="auto-min-score"
            className="input max-w-28"
            type="number"
            min={0}
            max={100}
            value={minScore}
            onChange={(event) => setMinScore(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label className="label" htmlFor="auto-daily-limit">
            Jobs a day
          </label>
          <input
            id="auto-daily-limit"
            className="input max-w-28"
            type="number"
            min={0}
            max={20}
            value={limit}
            onChange={(event) => setLimit(event.target.value)}
          />
        </div>
      </div>
      <p className="m-0 text-sm">
        {value.approved_today} jobs approved by auto mode today
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="btn self-start"
          disabled={!valid || save.isPending}
          onClick={() =>
            save.mutate({ enabled, min_score: score, daily_limit: perDay })
          }
        >
          Save auto mode
        </button>
        {save.isSuccess && (
          <span className="text-sm text-ok">Auto mode settings saved.</span>
        )}
      </div>
      {save.error && <ErrorNotice message={save.error.message} />}
    </Card>
  );
}

function AutoMode() {
  const { data, error, isPending } = useQuery({
    queryKey: ["auto-mode"],
    queryFn: getAutoMode,
  });
  if (isPending) return null;
  if (error) return <ErrorNotice message={error.message} />;
  return <AutoModeForm value={data} />;
}

const LINK_POLL_MS = 3000;
const TABS = ["Auto mode", "AI calls", "WhatsApp"] as const;
type Tab = (typeof TABS)[number];

function WhatsAppLinkPanel() {
  const client = useQueryClient();
  const { data, error } = useQuery({
    queryKey: ["whatsapp-link"],
    queryFn: getWhatsAppLink,
    // Keep checking until it is linked, so the QR code and the result appear by themselves.
    refetchInterval: (query) =>
      query.state.data?.state === "connected" ||
      query.state.data?.state === "disabled"
        ? false
        : LINK_POLL_MS,
  });
  const unlink = useMutation({
    mutationFn: unlinkWhatsApp,
    onSettled: () => client.invalidateQueries({ queryKey: ["whatsapp-link"] }),
  });

  return (
    <Card title="WhatsApp link">
      {error && <ErrorNotice message={error.message} />}
      {!data && !error && (
        <p className="m-0 text-sm text-muted">Checking WhatsApp…</p>
      )}
      {data?.state === "disabled" && (
        <InfoNotice message={data.error ?? "Not set up."} />
      )}
      {data?.state === "offline" && (
        <InfoNotice message="The WhatsApp service isn't running. In a new terminal run: cd whatsapp-service, then npm install (first time only), then npm start. This page updates by itself." />
      )}
      {data?.state === "qr" && data.qr && (
        <div className="flex flex-wrap items-start gap-5">
          <img
            src={data.qr}
            alt="WhatsApp QR code"
            width={264}
            height={264}
            className="rounded-lg border border-line bg-white p-2"
          />
          <ol className="m-0 flex flex-col gap-1.5 pl-5 text-sm">
            <li>Open WhatsApp on your phone.</li>
            <li>Go to Settings, then Linked devices, then Link a device.</li>
            <li>Scan this code. It refreshes by itself every few seconds.</li>
          </ol>
        </div>
      )}
      {data &&
        ["starting", "reconnecting", "logged_out"].includes(data.state) && (
          <p className="m-0 text-sm text-muted">Connecting to WhatsApp…</p>
        )}
      {data?.state === "connected" && (
        <>
          <p className="m-0 text-sm font-semibold text-ok">
            Linked to {data.me}
          </p>
          <button
            type="button"
            className="btn self-start"
            disabled={unlink.isPending}
            onClick={() => unlink.mutate()}
          >
            Unlink WhatsApp
          </button>
        </>
      )}
      {data?.state === "error" && (
        <ErrorNotice message={data.error ?? "WhatsApp link failed."} />
      )}
      {unlink.error && <ErrorNotice message={unlink.error.message} />}
      <p className="m-0 text-[13px] text-muted">
        This uses WhatsApp Web, which isn't an official WhatsApp product, so
        keep it to your own updates. Messages to your own number appear in
        "Message yourself" and may arrive silently.
      </p>
    </Card>
  );
}

export default function Settings() {
  const client = useQueryClient();
  const { data, error, isPending } = useQuery({
    queryKey: ["phase4"],
    queryFn: getPhase4,
  });
  const call = useMutation({
    mutationFn: testCall,
    onSuccess: (view) => client.setQueryData(["phase4"], view),
  });
  const whatsapp = useMutation({
    mutationFn: testWhatsApp,
    onSuccess: (view) => client.setQueryData(["phase4"], view),
  });

  const [tab, setTab] = useState<Tab>("Auto mode");

  if (isPending) return <p className="text-muted">Loading settings…</p>;
  if (error) return <ErrorNotice message={error.message} />;
  const recent = data.recent_calls ?? [];

  return (
    <>
      <header className="flex flex-col gap-1.5">
        <h1 className="m-0 font-display text-[28px] font-extrabold tracking-tight">
          Settings
        </h1>
        <p className="m-0 max-w-3xl text-muted">
          Auto mode, AI phone calls and WhatsApp. Calls and WhatsApp updates are
          switched on in backend/.env.
        </p>
      </header>

      <div
        role="tablist"
        aria-label="Settings sections"
        className="inline-flex flex-wrap gap-1 self-start rounded-xl bg-column p-1"
      >
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            className={`min-h-11 cursor-pointer rounded-lg border-0 px-4 text-sm font-semibold ${
              tab === name
                ? "bg-white text-brand-dark shadow-sm"
                : "bg-transparent text-muted"
            }`}
            onClick={() => setTab(name)}
          >
            {name}
          </button>
        ))}
      </div>

      {tab === "Auto mode" && <AutoMode />}

      {tab === "AI calls" && (
        <>
          <Card title="AI phone calls">
            <p className="m-0 text-sm">
              When an emailed application gets no reply after two follow-ups, an
              AI assistant calls the employer's published business number, says
              it is calling for you, and asks where to send your resume. Calls
              go out Monday to Friday, 9:30 to 4:30 NZ time.
            </p>
            {data.calls.configured ? (
              <>
                <p className="m-0 text-sm">
                  Automatic calls:{" "}
                  <b className={data.calls.enabled ? "text-ok" : "text-muted"}>
                    {data.calls.enabled ? "On" : "Off"}
                  </b>
                  {!data.calls.enabled &&
                    " (add CALLS_ENABLED=true to switch them on)"}
                </p>
                <p className="m-0 text-sm">
                  {data.calls.used_this_month} of {data.calls.monthly_limit}{" "}
                  calls used this month
                </p>
                <button
                  type="button"
                  className="btn self-start"
                  disabled={call.isPending}
                  onClick={() => call.mutate()}
                >
                  Test call to my phone
                </button>
                {call.isSuccess && (
                  <SuccessNotice message="Calling your phone now." />
                )}
                {call.error && <ErrorNotice message={call.error.message} />}
              </>
            ) : (
              <InfoNotice message="Not set up. Create an outgoing agent in your OmniDimension dashboard (set its maximum call length to 3 minutes), then add OMNIDIM_API_KEY and OMNIDIM_AGENT_ID to backend/.env and restart the backend." />
            )}
          </Card>
          {recent.length > 0 && (
            <Card title="Recent calls">
              <ul className="m-0 flex list-none flex-col gap-2 p-0">
                {recent.map((item) => (
                  <CallRow key={item.id} call={item} />
                ))}
              </ul>
            </Card>
          )}
        </>
      )}

      {tab === "WhatsApp" && (
        <>
          <WhatsAppLinkPanel />
          <Card title="WhatsApp updates">
            <p className="m-0 text-sm">
              Updates go only to you: new shortlisted jobs, resumes ready,
              replies, follow-ups due, finished calls and failed emails. Nothing
              is sent to employers on WhatsApp.
            </p>
            {data.whatsapp.configured ? (
              <>
                <p className="m-0 text-sm">Sending to {data.whatsapp.to}</p>
                <button
                  type="button"
                  className="btn self-start"
                  disabled={whatsapp.isPending}
                  onClick={() => whatsapp.mutate()}
                >
                  Send me a test WhatsApp
                </button>
                {whatsapp.isSuccess && (
                  <SuccessNotice message="Test WhatsApp sent." />
                )}
                {whatsapp.error && (
                  <ErrorNotice message={whatsapp.error.message} />
                )}
              </>
            ) : (
              <InfoNotice message="Not set up. Add WHATSAPP_ENABLED=true and WHATSAPP_TO (your number, +64…) to backend/.env and restart the backend." />
            )}
          </Card>
        </>
      )}
    </>
  );
}
