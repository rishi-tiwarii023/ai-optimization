export default function Toggle({ checked, onChange, label }) {
  return (
    <label className="inline-flex cursor-pointer select-none items-center gap-2">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 rounded-full ${
          checked ? "bg-zinc-900" : "bg-zinc-300"
        }`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-transform ${
            checked ? "left-4" : "left-0.5"
          }`}
        />
      </button>
      {label ? <span className="text-sm text-zinc-700">{label}</span> : null}
    </label>
  );
}
