import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { ProfileView } from "../api/profile";
import { mockApi, renderPage, type Call } from "../test/utils";
import Profile from "./Profile";

function profile(overrides: Partial<ProfileView> = {}): ProfileView {
  return {
    is_example: false,
    filename: "resume.pdf",
    titles: ["Python Developer"],
    skills: [
      { name: "Python", years: 2, level: null },
      { name: "SQL", years: null, level: null },
    ],
    tools: [],
    industries: ["Logistics"],
    seniority: "junior",
    search_queries: ["Python Developer Auckland"],
    regions: ["Auckland"],
    work_rights: "open_visa",
    salary_min: 65000,
    avoid_keywords: ["senior"],
    shortlist_threshold: 70,
    boards: [],
    connections: { claude: true, gemini: false, trademe: false, gmail: false, places: false, tavily: false },
    warning: null,
    contact: { name: "Sample Person", email: "sample@example.invalid", phone: "021 000 0000" },
    closed_outside_areas: 0,
    ...overrides,
  };
}

const deepSearch = () => ({
  body: { enabled: false, monthly_limit: 30, used_this_month: 0, available: true },
});

function withProfile(initial: ProfileView, extra = {}) {
  let current = initial;
  return mockApi({
    "GET /profile": () => ({ body: current }),
    "GET /deep-search": deepSearch,
    "PUT /profile": (body) => {
      current = { ...current, ...(body as Partial<ProfileView>) };
      return { body: current };
    },
    ...extra,
  });
}

const savedBody = (calls: Call[]) =>
  calls.find((call) => call.method === "PUT")?.body as Partial<ProfileView>;

describe("Profile", () => {
  it("shows what was read from the resume", async () => {
    withProfile(profile());
    renderPage(<Profile />);

    expect(await screen.findByText("resume.pdf")).toBeInTheDocument();
    expect(screen.getByText("Python Developer")).toBeInTheDocument();
    expect(screen.getByText("Python · 2 yrs")).toBeInTheDocument();
    expect(screen.getByText("SQL")).toBeInTheDocument();
    expect(screen.getByLabelText("Work rights")).toHaveValue("open_visa");
  });

  it("labels the example profile", async () => {
    withProfile(profile({ is_example: true, filename: null }));
    renderPage(<Profile />);

    expect(await screen.findByText("Example data")).toBeInTheDocument();
    expect(screen.getByText(/upload your resume/i)).toBeInTheDocument();
  });

  it("uploads a resume and shows any warning", async () => {
    const calls = withProfile(profile(), {
      "POST /profile/resume": () => ({
        body: profile({ filename: "new.pdf", warning: "Please check your titles and skills." }),
      }),
    });
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    const file = new File(["%PDF-"], "new.pdf", { type: "application/pdf" });
    await user.upload(screen.getByLabelText("Upload resume"), file);

    expect(await screen.findByRole("status")).toHaveTextContent("check your titles");
    const upload = calls.find((call) => call.path === "/profile/resume")!;
    expect((upload.body as FormData).get("file")).toBeInstanceOf(File);
  });

  it("shows why an upload failed", async () => {
    withProfile(profile(), {
      "POST /profile/resume": () => ({
        status: 400,
        body: { detail: "This file is not a valid PDF." },
      }),
    });
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.upload(
      screen.getByLabelText("Upload resume"),
      new File(["x"], "bad.pdf", { type: "application/pdf" }),
    );

    expect(await screen.findByRole("alert")).toHaveTextContent("not a valid PDF");
  });

  it("saves edited skills, searches and preferences", async () => {
    const calls = withProfile(profile());
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.click(screen.getByRole("button", { name: "Remove SQL" }));
    await user.type(screen.getByLabelText("Add a skill"), "Docker{Enter}");
    await user.type(screen.getByLabelText("Add a search"), "API developer Wellington{Enter}");
    await user.click(screen.getByLabelText("Wellington"));
    await user.selectOptions(screen.getByLabelText("Work rights"), "resident");
    await user.clear(screen.getByLabelText("Lowest salary (NZ$ a year)"));
    await user.type(screen.getByLabelText("Lowest salary (NZ$ a year)"), "80000");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByText("Profile saved.");
    const body = savedBody(calls);
    expect(body.skills?.map((skill) => skill.name)).toEqual(["Python", "Docker"]);
    expect(body.search_queries).toEqual(["Python Developer Auckland", "API developer Wellington"]);
    expect(body.regions).toEqual(["Auckland", "Wellington"]);
    expect(body.work_rights).toBe("resident");
    expect(body.salary_min).toBe(80000);
  });

  it("saves a blank salary and unknown work rights as empty", async () => {
    const calls = withProfile(profile());
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.clear(screen.getByLabelText("Lowest salary (NZ$ a year)"));
    await user.selectOptions(screen.getByLabelText("Work rights"), "");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByText("Profile saved.");
    expect(savedBody(calls).salary_min).toBeNull();
    expect(savedBody(calls).work_rights).toBeNull();
  });

  it("adds and removes a company careers board", async () => {
    const calls = withProfile(
      profile({ boards: [{ platform: "lever", token: "oldco", company: "Old Co" }] }),
    );
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("Old Co");

    await user.click(screen.getByRole("button", { name: "Remove Old Co" }));
    await user.selectOptions(screen.getByLabelText("Platform"), "greenhouse");
    await user.type(screen.getByLabelText("Board name"), "exampleco");
    await user.type(screen.getByLabelText("Company name"), "Example Co");
    await user.click(screen.getByRole("button", { name: "Add board" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByText("Profile saved.");
    expect(savedBody(calls).boards).toEqual([
      { platform: "greenhouse", token: "exampleco", company: "Example Co" },
    ]);
  });

  it("refuses an invalid board name", async () => {
    withProfile(profile());
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.type(screen.getByLabelText("Board name"), "../admin");
    await user.type(screen.getByLabelText("Company name"), "Example Co");
    await user.click(screen.getByRole("button", { name: "Add board" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Board name");
    expect(screen.queryByRole("button", { name: "Remove Example Co" })).toBeNull();
  });

  it("saves and then runs a search", async () => {
    const calls = withProfile(profile(), {
      "POST /runs/lead": () => ({
        body: { id: "r1", status: "ok", output: { new_jobs: 4, shortlisted: 2, errors: [] }, error: null },
      }),
    });
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.click(screen.getByRole("button", { name: "Save and run search" }));

    expect(await screen.findByText(/4 new jobs, 2 shortlisted/)).toBeInTheDocument();
    const order = calls.filter((call) => call.method !== "GET").map((call) => call.method);
    expect(order).toEqual(["PUT", "POST"]);
  });

  it("shows which services are connected", async () => {
    withProfile(profile());
    renderPage(<Profile />);

    const section = (await screen.findByRole("heading", { name: "Connections" })).closest("section")!;

    expect(within(section).getByText("Claude").parentElement).toHaveTextContent("Connected");
    expect(within(section).getByText("Trade Me").parentElement).toHaveTextContent("Not connected");
  });

  it("adds any New Zealand town", async () => {
    const calls = withProfile(profile());
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.type(screen.getByLabelText("Add a town or region"), " Timaru {Enter}");

    expect(screen.getByRole("checkbox", { name: "Timaru" })).toBeChecked();
    expect(screen.getByLabelText("Add a town or region")).toHaveValue("");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Profile saved.");
    expect(savedBody(calls).regions).toEqual(["Auckland", "Timaru"]);
  });

  it("keeps an added town visible after unticking it", async () => {
    const calls = withProfile(profile());
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.type(screen.getByLabelText("Add a town or region"), "Timaru{Enter}");
    await user.click(screen.getByRole("checkbox", { name: "Timaru" }));

    expect(screen.getByRole("checkbox", { name: "Timaru" })).not.toBeChecked();
    await user.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Profile saved.");
    expect(savedBody(calls).regions).toEqual(["Auckland"]);
  });

  it("ticks an existing place instead of adding a duplicate", async () => {
    const calls = withProfile(profile());
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.type(screen.getByLabelText("Add a town or region"), "wellington{Enter}");

    expect(screen.getAllByRole("checkbox", { name: /wellington/i })).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Profile saved.");
    expect(savedBody(calls).regions).toEqual(["Auckland", "Wellington"]);
  });

  it("can search all of New Zealand", async () => {
    const calls = withProfile(profile());
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");
    const everywhere = screen.getByRole("checkbox", { name: "All of New Zealand" });
    expect(everywhere).not.toBeChecked();

    await user.click(everywhere);

    expect(everywhere).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Auckland" })).not.toBeChecked();
    await user.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Profile saved.");
    expect(savedBody(calls).regions).toEqual([]);
  });

  it("turns off all of New Zealand when a place is chosen", async () => {
    withProfile(profile({ regions: [] }));
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");
    expect(screen.getByRole("checkbox", { name: "All of New Zealand" })).toBeChecked();

    await user.click(screen.getByRole("checkbox", { name: "Dunedin" }));

    expect(screen.getByRole("checkbox", { name: "All of New Zealand" })).not.toBeChecked();
  });

  it("saves your name and contact details for resumes", async () => {
    const calls = withProfile(profile());
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    expect(screen.getByLabelText("Full name")).toHaveValue("Sample Person");
    await user.clear(screen.getByLabelText("Full name"));
    await user.type(screen.getByLabelText("Full name"), "Sam Person");
    await user.clear(screen.getByLabelText("Phone"));
    await user.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByText("Profile saved.");
    expect(savedBody(calls).contact).toEqual({
      name: "Sam Person",
      email: "sample@example.invalid",
      phone: null,
    });
  });

  it("keeps unsaved edits when the profile refreshes in the background", async () => {
    withProfile(profile());
    const user = userEvent.setup();
    const { client } = renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.click(screen.getByRole("button", { name: "Remove SQL" }));
    await user.type(screen.getByLabelText("Board name"), "exampleco");
    await act(async () => {
      await client.invalidateQueries({ queryKey: ["profile"] });
      // React Query tells components about new data on a later tick.
      await new Promise((resolve) => setTimeout(resolve, 20));
    });

    expect(screen.queryByText("SQL")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Board name")).toHaveValue("exampleco");
  });

  it("shows the saved values after saving", async () => {
    withProfile(profile());
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.type(screen.getByLabelText("Add a skill"), "Docker{Enter}");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await screen.findByText("Profile saved.");
    expect(screen.getByText("Docker")).toBeInTheDocument();
  });

  it("shows the new resume's details after an upload", async () => {
    withProfile(profile(), {
      "POST /profile/resume": () => ({
        body: profile({ filename: "new.pdf", titles: ["Data Engineer"] }),
      }),
    });
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.upload(
      screen.getByLabelText("Upload resume"),
      new File(["%PDF-"], "new.pdf", { type: "application/pdf" }),
    );

    expect(await screen.findByText("Data Engineer")).toBeInTheDocument();
    expect(screen.queryByText("Python Developer")).not.toBeInTheDocument();
  });

  it("keeps edits and shows the error when saving fails", async () => {
    mockApi({
      "GET /profile": () => ({ body: profile() }),
      "GET /deep-search": deepSearch,
      "PUT /profile": () => ({ status: 500, body: { detail: "Database down" } }),
    });
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.click(screen.getByRole("button", { name: "Remove SQL" }));
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Database down"));
    expect(screen.queryByText("SQL")).not.toBeInTheDocument();
  });

  it("says how many jobs were closed outside the saved areas", async () => {
    withProfile(profile(), {
      "PUT /profile": (body: unknown) => ({
        body: { ...profile(), ...(body as object), closed_outside_areas: 1 },
      }),
    });
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Closed 1 job outside your areas.")).toBeInTheDocument();
  });

  it("counts jobs closed outside the saved areas", async () => {
    withProfile(profile(), {
      "PUT /profile": (body: unknown) => ({
        body: { ...profile(), ...(body as object), closed_outside_areas: 3 },
      }),
    });
    const user = userEvent.setup();
    renderPage(<Profile />);
    await screen.findByText("resume.pdf");

    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Closed 3 jobs outside your areas.")).toBeInTheDocument();
  });
});
