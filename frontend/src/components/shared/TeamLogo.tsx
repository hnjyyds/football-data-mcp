type Size = "xs" | "sm" | "md" | "lg";

const SIZE_CLASSES: Record<Size, string> = {
  xs: "w-6 h-6 text-xs",
  sm: "w-8 h-8 text-sm",
  md: "w-10 h-10 text-base",
  lg: "w-14 h-14 text-xl",
};

const PALETTE = ["#0f766e","#2563eb","#c2410c","#7c3aed","#be123c","#047857","#b45309","#155e75"];

function teamAccent(name: string): string {
  let hash = 0;
  for (let i = 0; i < name.length; i++) hash = (hash * 31 + name.charCodeAt(i)) % PALETTE.length;
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

function teamInitials(name: string): string {
  const clean = (name || "").replace(/\s+/g, " ").trim();
  if (!clean) return "FC";
  const compact = clean.replace(/[^\p{L}\p{N}一-鿿]/gu, "");
  const chinese = compact.match(/[一-鿿]/gu);
  if (chinese?.length) return chinese.slice(0, 2).join("");
  const parts = clean.split(/[\s·._-]+/).filter(Boolean);
  const initials = parts.length > 1 ? `${parts[0][0] || ""}${parts[1][0] || ""}` : compact.slice(0, 2);
  return (initials || "FC").toUpperCase();
}

export function TeamLogo({
  name,
  logoUrl,
  size = "sm",
}: {
  name: string;
  logoUrl?: string | null;
  size?: Size;
}) {
  const accent = teamAccent(name);
  const initials = teamInitials(name);
  return (
    <span
      className={`inline-flex items-center justify-center rounded-full font-bold text-white flex-shrink-0 ${SIZE_CLASSES[size]}`}
      style={{ backgroundColor: accent }}
      title={name}
      aria-label={`${name} 队徽`}
    >
      {logoUrl ? (
        <img src={logoUrl} alt="" loading="lazy" referrerPolicy="no-referrer" className="w-full h-full rounded-full object-cover" />
      ) : (
        <span>{initials}</span>
      )}
    </span>
  );
}

export function TeamMatchup({
  home,
  away,
  homeLogo,
  awayLogo,
  meta,
  size = "sm",
}: {
  home: string;
  away: string;
  homeLogo?: string | null;
  awayLogo?: string | null;
  meta?: string;
  size?: Size;
}) {
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <div className="flex items-center gap-2 min-w-0">
        <TeamLogo name={home} logoUrl={homeLogo} size={size} />
        <span className="font-medium text-slate-900 dark:text-slate-100 truncate text-sm">{home}</span>
      </div>
      <div className="flex items-center gap-2 min-w-0">
        <TeamLogo name={away} logoUrl={awayLogo} size={size} />
        <span className="font-medium text-slate-900 dark:text-slate-100 truncate text-sm">{away}</span>
      </div>
      {meta && <span className="text-xs text-slate-500 dark:text-slate-400 pl-10">{meta}</span>}
    </div>
  );
}
