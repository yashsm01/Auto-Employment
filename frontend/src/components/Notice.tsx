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

export function ExampleTag() {
  return (
    <span className="rounded-md bg-warn-soft px-2 py-1 text-[11px] font-semibold text-warn">
      Example data
    </span>
  );
}
