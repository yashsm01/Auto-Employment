import type { Template } from "../../api/masterCv";

export const DESIGNS: { id: Template; name: string; note: string }[] = [
  { id: "classic", name: "Classic", note: "Serif, centred name, ruled headings" },
  { id: "modern", name: "Modern", note: "Sans-serif with teal headings" },
  { id: "compact", name: "Compact", note: "Small type, fits more on one page" },
  { id: "executive", name: "Executive", note: "Navy headings under a contact rule" },
];

type Props = {
  value: Template;
  onChange: (template: Template) => void;
};

export default function DesignPicker({ value, onChange }: Props) {
  return (
    <fieldset className="m-0 flex flex-col gap-2 border-0 p-0">
      <legend className="label mb-2 p-0">Design</legend>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(min(100%,150px),1fr))] gap-2">
        {DESIGNS.map((design) => (
          <label
            key={design.id}
            className={`flex min-h-11 cursor-pointer flex-col gap-0.5 rounded-lg border px-3 py-2 text-sm ${
              value === design.id ? "border-brand bg-brand-soft" : "border-line bg-white"
            }`}
          >
            <span className="flex items-center gap-2 font-semibold">
              <input
                type="radio"
                name="cv-design"
                value={design.id}
                aria-label={design.name}
                checked={value === design.id}
                onChange={() => onChange(design.id)}
              />
              {design.name}
            </span>
            <span className="text-[12px] text-muted">{design.note}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
