import type { CSSProperties } from "react";

import type { CvDraft, Template } from "../../api/masterCv";

// Web-safe approximations of the four designs in the saved PDF and Word files.
type DesignStyle = {
  font: string;
  nameAlign: "center" | "left";
  nameCase: "uppercase" | "none";
  nameSize: number;
  bodySize: number;
  headingFont: string;
  headingColor: string;
  headingCase: "uppercase" | "none";
  headingSize: number;
  headingRule: string;
  contactRule: string;
  skillSeparator: string;
};

const DESIGN_STYLES: Record<Template, DesignStyle> = {
  classic: {
    font: "Georgia, serif",
    nameAlign: "center",
    nameCase: "uppercase",
    nameSize: 24,
    bodySize: 13,
    headingFont: "Georgia, serif",
    headingColor: "#000000",
    headingCase: "uppercase",
    headingSize: 13,
    headingRule: "1px solid #000000",
    contactRule: "none",
    skillSeparator: ", ",
  },
  modern: {
    font: "Inter, system-ui, sans-serif",
    nameAlign: "left",
    nameCase: "none",
    nameSize: 26,
    bodySize: 13,
    headingFont: "Inter, system-ui, sans-serif",
    headingColor: "#0F5C5C",
    headingCase: "uppercase",
    headingSize: 13,
    headingRule: "1px solid #0F5C5C",
    contactRule: "none",
    skillSeparator: ", ",
  },
  compact: {
    font: "Arial, Helvetica, sans-serif",
    nameAlign: "left",
    nameCase: "none",
    nameSize: 18,
    bodySize: 11,
    headingFont: "Arial, Helvetica, sans-serif",
    headingColor: "#000000",
    headingCase: "uppercase",
    headingSize: 11,
    headingRule: "1px solid #999999",
    contactRule: "none",
    skillSeparator: " · ",
  },
  executive: {
    font: "Cambria, Georgia, serif",
    nameAlign: "left",
    nameCase: "none",
    nameSize: 24,
    bodySize: 13,
    headingFont: "Cambria, Georgia, serif",
    headingColor: "#1F3A5F",
    headingCase: "none",
    headingSize: 15,
    headingRule: "none",
    contactRule: "2px solid #1F3A5F",
    skillSeparator: ", ",
  },
};

type Props = {
  draft: CvDraft;
};

const sectionHeading = (style: DesignStyle, text: string) => (
  <h3
    style={{
      margin: "14px 0 6px",
      fontFamily: style.headingFont,
      fontSize: style.headingSize,
      fontWeight: 700,
      color: style.headingColor,
      textTransform: style.headingCase,
      borderBottom: style.headingRule,
      paddingBottom: 2,
    }}
  >
    {text}
  </h3>
);

export default function CvPreview({ draft }: Props) {
  const { contact, sections, template } = draft;
  const style = DESIGN_STYLES[template];
  const contactLine = [
    contact.email,
    contact.phone,
    contact.location,
    contact.linkedin,
    contact.whatsapp && `WhatsApp ${contact.whatsapp}`,
    contact.work_rights,
  ]
    .filter(Boolean)
    .join(" · ");
  const hasInterests = sections.interests.trim() !== "";

  const root: CSSProperties = {
    fontFamily: style.font,
    fontSize: style.bodySize,
    color: "#111111",
    background: "#ffffff",
    border: "1px solid #e5e9f0",
    borderRadius: 6,
    padding: "24px 28px",
    lineHeight: 1.45,
  };

  return (
    <section aria-label="CV preview" data-template={template} style={root}>
      <header style={{ textAlign: style.nameAlign }}>
        <div
          style={{
            fontSize: style.nameSize,
            fontWeight: 700,
            textTransform: style.nameCase,
            color: template === "executive" ? style.headingColor : "inherit",
          }}
        >
          {contact.name || "Your name"}
        </div>
        {sections.headline && <div style={{ fontStyle: "italic" }}>{sections.headline}</div>}
        {contactLine && (
          <div style={{ fontSize: style.bodySize - 1, marginTop: 4 }}>{contactLine}</div>
        )}
        {template === "executive" && (
          <div style={{ borderBottom: style.contactRule, marginTop: 8 }} />
        )}
      </header>

      {/* The four core headings always print, as they do in the PDF and Word files. */}
      {sectionHeading(style, "Profile")}
      <p style={{ margin: 0, whiteSpace: "pre-line" }}>{sections.summary}</p>

      {sectionHeading(style, "Key skills")}
      <p style={{ margin: 0 }}>{sections.skills.join(style.skillSeparator)}</p>

      {sectionHeading(style, "Work history")}
      {sections.roles.map((role, index) => (
            <div key={index} style={{ marginBottom: 10 }}>
              <div style={{ display: "flex", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                <b>
                  {role.title}
                  {role.employer && `, ${role.employer}`}
                </b>
                <span>{[role.location, role.dates].filter(Boolean).join(" · ")}</span>
              </div>
              {role.bullets.length > 0 && (
                <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                  {role.bullets.map((bullet) => (
                    <li key={bullet.id}>{bullet.text}</li>
                  ))}
                </ul>
              )}
            </div>
      ))}

      {sectionHeading(style, "Education and certifications")}
      <ul style={{ margin: 0, paddingLeft: 18 }}>
        {sections.education.map((line, index) => (
          <li key={index}>{line}</li>
        ))}
      </ul>

      {hasInterests && (
        <>
          {sectionHeading(style, "Interests")}
          <p style={{ margin: 0 }}>{sections.interests}</p>
        </>
      )}

      {sectionHeading(style, "Referees")}
      <p style={{ margin: 0 }}>{sections.referees}</p>
    </section>
  );
}
