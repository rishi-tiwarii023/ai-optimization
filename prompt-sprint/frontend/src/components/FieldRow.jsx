export default function FieldRow({ label, hint, children }) {
  return (
    <div className="grid grid-cols-1 gap-2 border-b border-zinc-200 py-3 sm:grid-cols-[200px_1fr] sm:items-start sm:gap-4">
      <div>
        <div className="text-sm font-medium text-zinc-800">{label}</div>
        {hint ? <div className="mt-0.5 text-xs text-zinc-500">{hint}</div> : null}
      </div>
      <div>{children}</div>
    </div>
  );
}
