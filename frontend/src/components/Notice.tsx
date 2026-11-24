import type { ReactNode } from "react";

export function ErrorNotice({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-xl border border-bad/30 bg-bad-soft px-4 py-3 text-sm text-bad">
      {message}
    </div>
  );
}

export function SuccessNotice({ message }: { message: string }) {
  return (
    <div role="status" className="rounded-xl bg-ok-soft px-4 py-3 text-sm font-medium text-ok">
      {message}
    </div>
  );
}

export function InfoNotice({ message, children }: { message: string; children?: ReactNode }) {
  return (
    <div
      role="status"
      className="flex flex-col gap-2 rounded-xl border border-brand/30 bg-brand-soft px-4 py-3 text-sm text-brand-dark"
    >
      <span>{message}</span>
      {children && <div className="flex flex-wrap gap-4 font-semibold">{children}</div>}
    </div>
  );
}

export function ExampleTag() {
  return (
    <span className="rounded-md bg-warn-soft px-2 py-1 text-[11px] font-semibold text-warn">
      Example data
    </span>
  );
}
