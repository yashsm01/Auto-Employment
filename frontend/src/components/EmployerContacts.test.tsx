import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { components } from "../types/api";
import EmployerContacts from "./EmployerContacts";

type Contacts = components["schemas"]["EmployerContacts"];

function contacts(overrides: Partial<Contacts> = {}): Contacts {
  return {
    phone: "03 000 0000",
    phone_source: "Google Maps",
    emails: ["info@acme.co.nz"],
    hiring_emails: ["jobs@acme.co.nz"],
    website: "https://acme.co.nz/",
    contact_page: "https://acme.co.nz/contact",
    careers_page: "https://acme.co.nz/careers",
    linkedin: "https://www.linkedin.com/company/acme",
    hours: ["Monday: 9:00 AM – 5:00 PM", "Saturday: Closed"],
    rating: 4.6,
    rating_count: 120,
    recruiters: [
      {
        name: "Sam Reid",
        role: "Talent lead",
        email: "sam@acme.co.nz",
        phone: "021 000 000",
        source_url: "https://acme.co.nz/team",
      },
    ],
    checked_at: "2026-11-25T20:00:00Z",
    notes: ["Could not read the careers page (timed out)."],
    ...overrides,
  };
}

describe("EmployerContacts", () => {
  it("shows each contact with where it came from", () => {
    render(<EmployerContacts contacts={contacts()} />);

    const phone = screen.getByRole("link", { name: "03 000 0000" });
    expect(phone).toHaveAttribute("href", "tel:030000000");
    expect(screen.getByRole("link", { name: "info@acme.co.nz" })).toHaveAttribute(
      "href",
      "mailto:info@acme.co.nz",
    );
    expect(screen.getByRole("link", { name: "jobs@acme.co.nz" })).toHaveAttribute(
      "href",
      "mailto:jobs@acme.co.nz",
    );
    expect(screen.getByText("Sam Reid")).toBeInTheDocument();
    expect(screen.getByText("Talent lead")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "sam@acme.co.nz" })).toHaveAttribute(
      "href",
      "mailto:sam@acme.co.nz",
    );
    expect(screen.getAllByText("Hiring")).toHaveLength(2);
    expect(screen.getAllByText("Website").length).toBeGreaterThanOrEqual(3);
    expect(screen.getAllByText("Google Maps").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("★ 4.6 (120)")).toBeInTheDocument();
    expect(screen.getByText("Checked 26 Nov 2026")).toBeInTheDocument();
    expect(screen.getByText("Could not read the careers page (timed out).")).toBeInTheDocument();
  });

  it("links the website, contact page, careers page and LinkedIn in a new tab", () => {
    render(<EmployerContacts contacts={contacts()} />);

    const linkedin = screen.getByRole("link", { name: "LinkedIn" });
    expect(linkedin).toHaveAttribute("href", "https://www.linkedin.com/company/acme");
    expect(linkedin).toHaveAttribute("target", "_blank");
    expect(linkedin).toHaveAttribute("rel", "noopener noreferrer");

    for (const name of ["Website", "Contact page", "Careers page"]) {
      const link = screen.getAllByRole("link", { name }).find((el) => el.tagName === "A")!;
      expect(link).toHaveAttribute("target", "_blank");
      expect(link).toHaveAttribute("rel", "noopener noreferrer");
    }
  });

  it("puts opening hours in a details element", () => {
    render(<EmployerContacts contacts={contacts()} />);

    const hours = screen.getByText("Opening hours").closest("details")!;
    expect(hours).toBeInTheDocument();
    expect(within(hours).getByText("Monday: 9:00 AM – 5:00 PM")).toBeInTheDocument();
  });

  it("does not render unsafe URLs as links", () => {
    render(
      <EmployerContacts
        contacts={contacts({ website: "javascript:alert(1)", linkedin: "not a url" })}
      />,
    );

    expect(screen.queryByRole("link", { name: "LinkedIn" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Website" })).toBeNull();
  });

  it("says so when no phone, email, hiring contact or page was found", () => {
    render(
      <EmployerContacts
        contacts={{
          website: "https://acme.co.nz/",
          notes: ["Could not read the website (timed out)."],
        }}
      />,
    );

    expect(screen.getByText("No contact details found yet.")).toBeInTheDocument();
    expect(screen.getByText("Could not read the website (timed out).")).toBeInTheDocument();
  });

  it("calls onRefresh from the Get contact details button", async () => {
    const onRefresh = vi.fn();
    const user = userEvent.setup();
    render(<EmployerContacts contacts={contacts()} onRefresh={onRefresh} />);

    await user.click(screen.getByRole("button", { name: "Get contact details" }));

    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it("disables the button while a lookup is running", () => {
    render(<EmployerContacts contacts={{}} onRefresh={() => {}} busy />);

    expect(screen.getByRole("button", { name: "Get contact details" })).toBeDisabled();
  });

  it("has no button when there is nothing to refresh from", () => {
    render(<EmployerContacts contacts={contacts()} />);

    expect(screen.queryByRole("button", { name: "Get contact details" })).toBeNull();
  });
});
