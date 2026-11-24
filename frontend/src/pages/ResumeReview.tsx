import { Link } from "react-router-dom";

import { ErrorNotice } from "../components/Notice";
import { useReviewList } from "../hooks/useResumes";

export default function ResumeReview() {
  const { data, error, isPending } = useReviewList();

  if (isPending) return <p className="text-muted">Loading resumes…</p>;
  if (error) return <ErrorNotice message={error.message} />;

  return (
    <>
      <header className="flex flex-col gap-1.5">
        <h1 className="m-0 font-display text-[28px] font-extrabold tracking-tight">Resume review</h1>
        <p className="m-0 max-w-3xl text-muted">
          A tailored resume and cover note for each job you approved. Nothing is sent until you
          approve it.
        </p>
      </header>

      {data.items.length === 0 && (
        <p className="card m-0 text-muted">
          No resumes to review yet. Approve a job on your Shortlist to start one.
        </p>
      )}

      <div className="flex flex-col gap-3">
        {data.items.map((item) => (
          <article key={item.application_id} className="card flex flex-wrap items-center justify-between gap-3">
            <div className="flex min-w-0 flex-col gap-1">
              <h2 className="m-0 text-base font-bold">{item.title}</h2>
              <span className="text-sm text-muted">{item.company}</span>
              {item.status === "ready" && (
                <span className="text-[13px] font-semibold text-ok">Ready for review</span>
              )}
              {item.status === "tailoring" && (
                <span className={`text-[13px] font-semibold ${item.error ? "text-bad" : "text-warn"}`}>
                  {item.error ? `Tailoring failed: ${item.error}` : "Tailoring your resume…"}
                </span>
              )}
            </div>
            <Link
              className={item.status === "ready" ? "btn btn-primary" : "btn"}
              to={`/jobs/${item.application_id}/resume`}
            >
              {item.status === "ready" ? "Review" : "Open"}
            </Link>
          </article>
        ))}
      </div>
    </>
  );
}
