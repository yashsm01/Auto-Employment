import { useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import {
  masterCvFileUrl,
  toDraft,
  type CvDraft,
  type MasterCV,
  type MasterCVView,
} from "../api/masterCv";
import AtsCheckPanel from "../components/builder/AtsCheckPanel";
import CvPreview from "../components/builder/CvPreview";
import DesignPicker from "../components/builder/DesignPicker";
import SectionsEditor from "../components/builder/SectionsEditor";
import { ErrorNotice, InfoNotice, SuccessNotice } from "../components/Notice";
import { useMasterCv, useSaveMasterCv } from "../hooks/useMasterCv";

type EditorProps = {
  view: MasterCVView;
  busy: boolean;
  onSave: (cv: MasterCV) => void;
};

// The editor keeps its own copy of the CV until Save CV sends it. The page remounts it after each save.
function Editor({ view, busy, onSave }: EditorProps) {
  const [draft, setDraft] = useState<CvDraft>(() => toDraft(view));

  // Disabling the whole editor while the PUT is in flight stops edits that the remount would discard.
  return (
    <fieldset disabled={busy} className="m-0 min-w-0 border-0 p-0">
    <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="flex min-w-0 flex-col gap-4">
        {view.source === "empty" && (
          <InfoNotice message="We couldn't read sections from your resume. Fill them in here." />
        )}
        <SectionsEditor draft={draft} update={(change) => setDraft((cv) => change(cv))} />
      </div>

      <div className="flex min-w-0 flex-col gap-4">
        <section className="card flex flex-col gap-4">
          <DesignPicker
            value={draft.template}
            onChange={(template) => setDraft((cv) => ({ ...cv, template }))}
          />
          <div className="flex flex-wrap items-center gap-2.5">
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => onSave(draft)}
            >
              {busy ? "Saving…" : "Save CV"}
            </button>
            <a
              className="btn"
              href={masterCvFileUrl("pdf")}
              target="_blank"
              rel="noopener noreferrer"
            >
              Download PDF
            </a>
            <a
              className="btn"
              href={masterCvFileUrl("docx")}
              target="_blank"
              rel="noopener noreferrer"
            >
              Download Word
            </a>
          </div>
          <p className="m-0 text-[13px] text-muted">
            Downloads use the last saved CV. Save first to include your latest changes.
          </p>
        </section>

        <CvPreview draft={draft} />
        <AtsCheckPanel ats={view.ats ?? null} />
      </div>
    </div>
    </fieldset>
  );
}

export default function ResumeBuilder() {
  const { data, error, isPending } = useMasterCv();
  const saveMutation = useSaveMasterCv();
  const [message, setMessage] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  // Changing this remounts the editor, so it starts again from the saved CV.
  const [formVersion, setFormVersion] = useState(0);

  if (isPending) return <p className="text-muted">Loading your resume builder…</p>;

  const header = (
    <header className="flex flex-col items-start gap-1.5">
      <h1 className="m-0 font-display text-[28px] font-extrabold tracking-tight">Resume builder</h1>
      <p className="m-0 text-muted">
        Edit your master CV, pick a design, and check how it reads to applicant tracking software.
      </p>
    </header>
  );

  // A failed refetch keeps the CV that is already loaded, so typed edits are not lost.
  if (error && !data) {
    const needsResume = error instanceof ApiError && error.status === 400;
    return (
      <>
        {header}
        <ErrorNotice message={error.message} />
        {needsResume && (
          <p className="m-0 text-sm">
            Upload a resume on{" "}
            <Link to="/profile" className="font-semibold text-brand">
              My resume profile
            </Link>
            .
          </p>
        )}
      </>
    );
  }

  const handleSave = async (cv: MasterCV) => {
    setMessage(null);
    setProblem(null);
    try {
      await saveMutation.mutateAsync(cv);
      setFormVersion((version) => version + 1);
      setMessage("CV saved.");
    } catch (failure) {
      setProblem((failure as Error).message);
    }
  };

  return (
    <>
      {header}
      {error && <ErrorNotice message={error.message} />}
      {message && <SuccessNotice message={message} />}
      {problem && <ErrorNotice message={problem} />}
      <Editor
        key={formVersion}
        view={data}
        busy={saveMutation.isPending}
        onSave={handleSave}
      />
    </>
  );
}
