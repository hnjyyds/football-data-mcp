export function BrandLogo({ size = 28, glow = false }: { size?: number; glow?: boolean }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={glow ? "drop-shadow-[0_8px_14px_rgba(0,0,0,0.12)]" : ""}
      aria-label="Football Strategy"
    >
      <rect x="1" y="1" width="30" height="30" rx="7" fill="hsl(var(--foreground))" />
      <path d="M8.5 9h15v14h-15z" stroke="hsl(var(--background))" strokeOpacity="0.84" strokeWidth="1.35" />
      <path d="M16 9v14M8.5 16h15" stroke="hsl(var(--background))" strokeOpacity="0.22" strokeWidth="1.1" />
      <circle cx="16" cy="16" r="3.1" stroke="hsl(var(--background))" strokeOpacity="0.26" strokeWidth="1.1" />
      <path
        d="M10 21c3.15-5.4 6.95-8.05 12-8.9"
        stroke="hsl(var(--background))"
        strokeWidth="1.8"
        strokeLinecap="round"
      />
      <circle cx="22" cy="12.1" r="1.8" fill="hsl(var(--background))" />
      <circle cx="10" cy="21" r="1.35" fill="hsl(var(--background))" />
    </svg>
  );
}

export function BrandWordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-display font-bold tracking-tight text-[hsl(var(--foreground))] ${className}`}>
      Pitch.AI
    </span>
  );
}
