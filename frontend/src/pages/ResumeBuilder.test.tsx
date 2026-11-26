import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { masterCvFileUrl, type MasterCVView } from "../api/masterCv";
import App from "../App";
import { mockApi, renderPage, type Call } from "../test/utils";
import ResumeBuilder from "./ResumeBuilder";

function view(overrides: Partial<MasterCVView> = {}): MasterCVView {
  return {
    contact: {
      name: "Aroha Test",
      email: "aroha@example.com",
      phone: "021 000 000",
      location: "Timaru",
      linkedin: "linkedin.com/in/aroha",
      whatsapp: "021 000 000",
      work_rights: "Citizen",
    },
    sections: {
      headline: "Customer success lead",
      summary: "Five years leading support teams.",
      roles: [
        {
          title: "Support lead",
          employer: "Acme Software",
          location: "Timaru",
          dates: "2020 – 2024",
          bullets: [{ id: "b1", text: "Led a team of four." }],
        },
      ],
      skills: ["Zendesk", "Coaching"],
      education: ["BCom, Lincoln University"],
      interests: "",
      referees: "Available on request.",
    },
    template: "classic",
    source: "resume",
    ats: {
      items: [
        { label: "Standard headings", ok: true, detail: "Found Profile and Work history." },
        { label: "Contact details in header", ok: false, detail: "Email sits in a text box." },
      ],
      text: "Aroha Test\nSupport lead, Acme Software",
      pages: 1,
      pdf_bytes: 4000,
      docx_bytes: 8000,
    },
    ...overrides,
  };
}

function withCv(current: MasterCVView) {
  let latest = current;
  const calls = mockApi({
    "GET /master-cv": () => ({ body: latest }),
    "PUT /master-cv": (body) => {
      const cv = body as MasterCVView;
      latest = { ...cv, source: "resume", ats: current.ats };
      return { body: latest };
    },
  });
  return calls;
}

const preview = () => screen.getByRole("region", { name: "CV preview" });

describe("ResumeBuilder", () => {
  it("shows the sections from the API", async () => {
    withCv(view());
    renderPage(<ResumeBuilder />, "/builder");

    expect(await screen.findByLabelText("Headline")).toHaveValue("Customer success lead");
    expect(screen.getByLabelText("Profile")).toHaveValue("Five years leading support teams.");
    expect(screen.getByLabelText("Work history role 1 job title")).toHaveValue("Support lead");
    expect(screen.getByRole("button", { name: "Remove Zendesk" })).toBeInTheDocument();

    const headings = within(preview())
      .getAllByRole("heading")
      .map((heading) => heading.textContent);
    expect(headings).toEqual([
      "Profile",
      "Key skills",
      "Work history",
      "Education and certifications",
      "Referees",
    ]);
  });

  it("choosing a design and saving sends the template", async () => {
    const user = userEvent.setup();
    const calls = withCv(view());
    renderPage(<ResumeBuilder />, "/builder");

    await user.click(await screen.findByLabelText("Modern"));
    await user.click(screen.getByRole("button", { name: "Save CV" }));

    expect(await screen.findByText("CV saved.")).toBeInTheDocument();
    const put = calls.find((call: Call) => call.method === "PUT");
    expect(put?.body).toMatchObject({ template: "modern" });
  });

  it("an edited role date is saved exactly as typed", async () => {
    const user = userEvent.setup();
    const calls = withCv(view());
    renderPage(<ResumeBuilder />, "/builder");

    const dates = await screen.findByLabelText("Work history role 1 dates");
    await user.clear(dates);
    await user.type(dates, "Mar 2019 – Jun 2024 (part-time)");
    await user.click(screen.getByRole("button", { name: "Save CV" }));

    await screen.findByText("CV saved.");
    const put = calls.find((call: Call) => call.method === "PUT");
    const body = put?.body as MasterCVView;
    expect(body.sections.roles?.[0]?.dates).toBe("Mar 2019 – Jun 2024 (part-time)");
  });

  it("ATS items and the parse preview toggle show", async () => {
    const user = userEvent.setup();
    withCv(view());
    renderPage(<ResumeBuilder />, "/builder");

    expect(await screen.findByText("Standard headings")).toBeInTheDocument();
    expect(screen.getByText("Email sits in a text box.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Passed" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Needs attention" })).toBeInTheDocument();
    expect(screen.getByText("Saved files are checked. Save to update the check.")).toBeInTheDocument();

    expect(document.querySelector("pre")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Show what ATS software reads" }));
    expect(document.querySelector("pre")).toHaveTextContent("Support lead, Acme Software");
    await user.click(screen.getByRole("button", { name: "Hide what ATS software reads" }));
    expect(document.querySelector("pre")).toBeNull();
  });

  it("the empty form message shows when nothing was read", async () => {
    withCv(
      view({
        source: "empty",
        sections: {
          headline: "",
          summary: "",
          roles: [],
          skills: [],
          education: [],
          interests: "",
          referees: "Available on request.",
        },
        ats: null,
      }),
    );
    renderPage(<ResumeBuilder />, "/builder");

    expect(
      await screen.findByText("We couldn't read sections from your resume. Fill them in here."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /ATS software reads/ })).toBeNull();
  });

  it("the menu has Resume builder after Shortlist", async () => {
    withCv(view());
    renderPage(<App />, "/builder");

    const nav = await screen.findByRole("navigation", { name: "Main" });
    const labels = within(nav)
      .getAllByRole("link")
      .map((link) => link.textContent ?? "");
    const shortlist = labels.findIndex((label) => label.startsWith("Shortlist"));
    const builder = labels.findIndex((label) => label.startsWith("Resume builder"));
    expect(shortlist).toBeGreaterThanOrEqual(0);
    expect(builder).toBe(shortlist + 1);
    expect(within(nav).getByRole("link", { name: "Resume builder" })).toHaveAttribute(
      "href",
      "/builder",
    );
  });

  it("download links point at the PDF and Word files", async () => {
    withCv(view());
    renderPage(<ResumeBuilder />, "/builder");

    const pdf = await screen.findByRole("link", { name: "Download PDF" });
    expect(pdf).toHaveAttribute("href", masterCvFileUrl("pdf"));
    expect(pdf).toHaveAttribute("target", "_blank");
    expect(pdf).toHaveAttribute("rel", "noopener noreferrer");
    expect(screen.getByRole("link", { name: "Download Word" })).toHaveAttribute(
      "href",
      masterCvFileUrl("docx"),
    );
    expect(masterCvFileUrl("docx")).toContain("/master-cv/file?format=docx");
  });

  it("asks for a resume upload when there is no base resume", async () => {
    mockApi({
      "GET /master-cv": () => ({
        status: 400,
        body: { detail: "Upload your resume first, then build on it here." },
      }),
    });
    renderPage(<ResumeBuilder />, "/builder");

    expect(
      await screen.findByText("Upload your resume first, then build on it here."),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "My resume profile" })).toHaveAttribute(
      "href",
      "/profile",
    );
  });

  it("shows the profile word count as the profile is typed", async () => {
    const user = userEvent.setup();
    withCv(view());
    renderPage(<ResumeBuilder />, "/builder");

    const profile = await screen.findByLabelText("Profile");
    await user.clear(profile);
    await user.type(profile, "One two three four");
    expect(screen.getByText("4 words")).toBeInTheDocument();
  });

  it("shows the server message when a save is refused", async () => {
    const user = userEvent.setup();
    mockApi({
      "GET /master-cv": () => ({ body: view() }),
      "PUT /master-cv": () => ({
        status: 422,
        body: {
          detail: [{ loc: ["body", "sections", "roles"], msg: "sections.roles has 21 items; the limit is 20." }],
        },
      }),
    });
    renderPage(<ResumeBuilder />, "/builder");

    await user.click(await screen.findByRole("button", { name: "Save CV" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "sections.roles: sections.roles has 21 items; the limit is 20.",
    );
    await waitFor(() => expect(screen.queryByText("CV saved.")).toBeNull());
  });

  it("the preview always shows the five headings in file order, even for an empty CV", async () => {
    withCv(
      view({
        source: "empty",
        sections: {
          headline: "",
          summary: "",
          roles: [],
          skills: [],
          education: [],
          interests: "",
          referees: "Available on request.",
        },
        ats: null,
      }),
    );
    renderPage(<ResumeBuilder />, "/builder");

    await screen.findByRole("region", { name: "CV preview" });
    const headings = within(preview())
      .getAllByRole("heading")
      .map((heading) => heading.textContent);
    expect(headings).toEqual([
      "Profile",
      "Key skills",
      "Work history",
      "Education and certifications",
      "Referees",
    ]);
  });

  it("a failed refetch keeps the typed draft and shows the error above the editor", async () => {
    const user = userEvent.setup();
    let fail = false;
    mockApi({
      "GET /master-cv": () =>
        fail ? { status: 500, body: { detail: "The server is busy." } } : { body: view() },
    });
    const { client } = renderPage(<ResumeBuilder />, "/builder");
    const summary = await screen.findByLabelText("Profile");
    await user.type(summary, " Typed but not saved.");

    fail = true;
    await act(async () => {
      await client.refetchQueries({ queryKey: ["master-cv"] });
    });

    expect(await screen.findByText("The server is busy.", undefined, { timeout: 6000 })).toBeVisible();
    expect(screen.getByLabelText("Profile")).toHaveValue(
      "Five years leading support teams. Typed but not saved.",
    );
  }, 15000);

  it("the editor is disabled while a save is in flight and shows the server values afterwards", async () => {
    const user = userEvent.setup();
    const current = view();
    const saved = view({
      sections: { ...current.sections, summary: "Server summary from the save." },
    });
    let release: () => void = () => {};
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        const method = init?.method ?? "GET";
        if (method === "PUT") {
          await held;
          return new Response(JSON.stringify(saved), { status: 200 });
        }
        return new Response(JSON.stringify(current), { status: 200 });
      }),
    );
    renderPage(<ResumeBuilder />, "/builder");

    await screen.findByLabelText("Profile");
    await user.click(screen.getByRole("button", { name: "Save CV" }));
    expect(await screen.findByRole("button", { name: "Saving…" })).toBeDisabled();
    expect(screen.getByLabelText("Profile")).toBeDisabled();

    release();
    await screen.findByText("CV saved.");
    await waitFor(() => expect(screen.getByLabelText("Profile")).toBeEnabled());
    expect(screen.getByLabelText("Profile")).toHaveValue("Server summary from the save.");
  });
});
