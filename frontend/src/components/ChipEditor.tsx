import { useId, useState, type KeyboardEvent } from "react";

type Props = {
  items: { key: string; label: string }[];
  addLabel: string;
  placeholder?: string;
  onAdd: (value: string) => void;
  onRemove: (key: string) => void;
};

export default function ChipEditor({ items, addLabel, placeholder, onAdd, onRemove }: Props) {
  const inputId = useId();
  const [draft, setDraft] = useState("");

  const add = () => {
    const value = draft.trim();
    if (value) onAdd(value);
    setDraft("");
  };

  const handleKey = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter") {
      event.preventDefault();
      add();
    }
  };

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={item.key}
            className="inline-flex items-center gap-1 rounded-md bg-ok-soft py-0.5 pr-0.5 pl-2 text-xs text-ok"
          >
            <span>{item.label}</span>
            <button
              type="button"
              aria-label={`Remove ${item.key}`}
              className="grid size-6 cursor-pointer place-items-center rounded border-0 bg-transparent text-sm text-ok hover:bg-white"
              onClick={() => onRemove(item.key)}
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <label htmlFor={inputId} className="sr-only">
          {addLabel}
        </label>
        <input
          id={inputId}
          className="input min-w-0 flex-1"
          value={draft}
          placeholder={placeholder ?? addLabel}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKey}
        />
        <button type="button" className="btn" aria-label={`${addLabel} now`} onClick={add}>
          Add
        </button>
      </div>
    </div>
  );
}
