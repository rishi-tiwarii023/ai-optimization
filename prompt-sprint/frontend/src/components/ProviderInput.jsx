export default function ProviderInput({
  id = "provider-options",
  value,
  onChange,
  onBlur,
  providers,
  placeholder = "LiteLLM provider id",
  className = "input max-w-sm",
}) {
  return (
    <>
      <input
        className={className}
        list={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onBlur={onBlur}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
      />
      <datalist id={id}>
        {providers.map((item) => (
          <option key={item.name} value={item.name} />
        ))}
      </datalist>
    </>
  );
}
