import { NavLink, Outlet } from "react-router-dom";

import { useShortlist } from "../hooks/useShortlist";

const LATER = ["Resume review", "Outbox and follow-ups", "My resume profile", "Settings"];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `flex min-h-11 flex-1 items-center justify-between gap-2 rounded-lg px-3 text-sm font-medium no-underline md:flex-none ${
    isActive ? "bg-brand text-white" : "text-nav hover:bg-navy-light hover:text-white"
  }`;

export default function Layout() {
  const shortlist = useShortlist();
  const count = shortlist.data?.items.length;

  return (
    <div className="flex min-h-screen flex-col bg-page md:flex-row">
      <nav
        aria-label="Main"
        className="flex shrink-0 flex-wrap gap-1 bg-navy px-3.5 py-3 text-white md:w-60 md:flex-col md:flex-nowrap md:py-5"
      >
        <div className="flex w-full items-center gap-2.5 px-2 pb-2 font-display text-[17px] font-extrabold md:pb-4">
          <span className="grid size-8 place-items-center rounded-[9px] bg-brand text-[13px]">
            JA
          </span>
          Job Autopilot
        </div>
        <NavLink to="/" end className={linkClass}>
          Pipeline
        </NavLink>
        <NavLink to="/shortlist" className={linkClass}>
          Shortlist
          {count !== undefined && (
            <span className="rounded-full bg-navy-light px-2 text-xs text-white">{count}</span>
          )}
        </NavLink>
        {LATER.map((name) => (
          <span
            key={name}
            className="hidden min-h-11 items-center justify-between rounded-lg px-3 text-sm text-nav-muted md:flex"
          >
            {name}
            <span className="text-[11px]">Soon</span>
          </span>
        ))}
      </nav>
      <main className="flex min-w-0 flex-1 flex-col gap-5 px-4 py-7 md:px-8">
        <Outlet />
      </main>
    </div>
  );
}
