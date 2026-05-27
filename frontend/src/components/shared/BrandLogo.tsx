export function BrandLogo({ size = 28, glow = false }: { size?: number; glow?: boolean }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={glow ? "drop-shadow-[0_0_8px_rgba(26,166,171,0.6)]" : ""}
      aria-label="Football Strategy"
    >
      <defs>
        <linearGradient id="brand-grad" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#3ec3c5" />
          <stop offset="60%" stopColor="#1aa6ab" />
          <stop offset="100%" stopColor="#0a5457" />
        </linearGradient>
        <linearGradient id="strike-grad" x1="0" y1="0" x2="0" y2="32" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#ff9425" />
          <stop offset="100%" stopColor="#f6720c" />
        </linearGradient>
      </defs>
      <rect x="0.5" y="0.5" width="31" height="31" rx="7.5" fill="url(#brand-grad)" />
      {/* Pentagon - classic football center */}
      <path
        d="M16 8.5 L21.5 12.5 L19.5 19 L12.5 19 L10.5 12.5 Z"
        fill="white"
        fillOpacity="0.95"
      />
      {/* Arrow upward - growth/strategy */}
      <path
        d="M16 21.5 L16 26 M16 21.5 L13.5 24 M16 21.5 L18.5 24"
        stroke="url(#strike-grad)"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function BrandWordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-display font-bold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-brand-600 to-brand-500 dark:from-brand-300 dark:to-brand-400 ${className}`}>
      Pitch<span className="text-strike-500 dark:text-strike-400">.</span>AI
    </span>
  );
}
