import { useEffect, useState } from "react";

type Size = "xs" | "sm" | "md" | "lg";

const SIZE_CLASSES: Record<Size, string> = {
  xs: "w-6 h-6 text-xs",
  sm: "w-8 h-8 text-sm",
  md: "w-10 h-10 text-base",
  lg: "w-14 h-14 text-xl",
};

const PROXIED_LOGO_HOSTS = new Set(["sd.qunliao.info"]);

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

function normalizeLogoUrl(value: string | null | undefined): string {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  if (raw.startsWith("//")) return `https:${raw}`;
  return raw;
}

function logoSrc(value: string | null | undefined): string {
  const raw = normalizeLogoUrl(value);
  if (!raw) return "";
  try {
    const parsed = new URL(raw);
    if (PROXIED_LOGO_HOSTS.has(parsed.hostname)) {
      return `/image-proxy?url=${encodeURIComponent(parsed.toString())}`;
    }
  } catch {
    return raw;
  }
  return raw;
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
  const initials = teamInitials(name);
  const [broken, setBroken] = useState(false);
  const src = logoSrc(logoUrl);

  useEffect(() => {
    setBroken(false);
  }, [logoUrl]);

  const showImage = !!src && !broken;
  return (
    <span
      className={`inline-flex items-center justify-center overflow-hidden rounded-full border border-[hsl(var(--border))] bg-[hsl(var(--card))] text-[hsl(var(--muted-foreground))] font-medium flex-shrink-0 ${SIZE_CLASSES[size]}`}
      title={name}
      aria-label={`${name} 队徽`}
    >
      {showImage ? (
        <img
          src={src}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setBroken(true)}
          className="h-full w-full rounded-full bg-white object-contain p-[2px]"
        />
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
        <span className="font-medium text-[hsl(var(--foreground))] truncate text-sm">{home}</span>
      </div>
      <div className="flex items-center gap-2 min-w-0">
        <TeamLogo name={away} logoUrl={awayLogo} size={size} />
        <span className="font-medium text-[hsl(var(--foreground))] truncate text-sm">{away}</span>
      </div>
      {meta && <span className="text-xs text-[hsl(var(--muted-foreground))] pl-10">{meta}</span>}
    </div>
  );
}
