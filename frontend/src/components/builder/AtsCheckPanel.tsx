import { useState } from "react";

import type { AtsReport } from "../../api/masterCv";

function StatusIcon({ ok }: { ok: boolean }) {
  return ok ? (
    <svg role="img" aria-label="Passed" viewBox="0 0 20 20" width="18" height="18" className="shrink-0 text-ok">
      <path
        d="M5 10.5l3.2 3.2L15 6.8"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  ) : (
    <svg role="img" aria-label="Needs attention" viewBox="0 0 20 20" width="18" height="18" className="shrink-0 text-warn">
      <path d="M10 3l8 14H2z" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" />
      <path d="M10 8v4M10 14.5v.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export default function AtsCheckPanel({ ats }: { ats: AtsReport | null }) {
  const [open, setOpen] = useState(false);
  if (!ats) return null;

  return (
    <section className="card flex flex-col gap-3" aria-label="ATS check">
      <h2 className="m-0 font-display text-[17px] font-bold">ATS check</h2>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {ats.items.map((item) => (
          <li key={item.label} className="flex items-start gap-2 text-sm">
            <StatusIcon ok={item.ok} />
            <span className="flex flex-col">
              <span className="font-semibold">{item.label}</span>
              {item.detail && <span className="text-[13px] text-muted">{item.detail}</span>}
            </span>
          </li>
        ))}
      </ul>
      <div>
        <button
          type="button"
          className="btn"
          aria-expanded={open}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Hide what ATS software reads" : "Show what ATS software reads"}
        </button>
      </div>
      {open && (
        <pre className="m-0 max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-page p-3 text-[12px]">
          {ats.text}
        </pre>
      )}
      <p className="m-0 text-[13px] text-muted">Saved files are checked. Save to update the check.</p>
    </section>
  );
}
