import { NavLink } from "react-router-dom";

const links = [
  { to: "/config", label: "Config" },
  { to: "/tasks", label: "Tasks" },
  { to: "/results", label: "Results" },
];

export default function Navbar() {
  return (
    <header className="border-b border-zinc-200 bg-white">
      <div className="mx-auto flex h-12 max-w-6xl items-center justify-between px-4">
        <div className="text-sm font-semibold tracking-tight text-zinc-900">
          PromptSprint
        </div>
        <nav className="flex items-stretch gap-1">
          {links.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `px-3 py-1.5 text-sm ${
                  isActive
                    ? "bg-zinc-900 text-white"
                    : "text-zinc-600 hover:bg-zinc-100 hover:text-zinc-900"
                }`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </header>
  );
}
