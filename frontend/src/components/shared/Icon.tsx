/**
 * Unified icon system.
 *
 * All UI icons must go through this layer so we have:
 * 1) A single registry of allowed icons (no random imports across files)
 * 2) Consistent stroke-width, size scale, and a11y attributes
 * 3) A swap point for replacing lucide-react with another library (Phosphor,
 *    Heroicons, Tabler, etc.) in one place
 * 4) Custom brand-specific icons (football, trophy variations, position
 *    glyphs) co-located with the rest
 */
import type { ReactElement } from "react";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ArrowDown,
  BarChart3,
  BrainCircuit,
  Calendar,
  CheckCircle2,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  CircleCheck,
  CircleHelp,
  Clock,
  CloudSun,
  Database,
  Eye,
  Filter,
  Flag,
  Gauge,
  History,
  Hourglass,
  Info,
  ListChecks,
  Loader,
  Lock,
  Menu,
  MoreHorizontal,
  Moon,
  Rocket,
  RefreshCw,
  Search,
  Settings,
  Settings2,
  ShieldCheck,
  Sparkles,
  Star,
  Sun,
  Target,
  TrendingDown,
  TrendingUp,
  Trophy,
  Unlock,
  UserRound,
  UsersRound,
  X,
  XCircle,
  Zap,
  MapPin,
  type LucideIcon,
} from "lucide-react";

/* ─── Custom SVG icons ───────────────────────────────────────────────────── */

type IconProps = { size?: number; className?: string; "aria-label"?: string };

function Football({ size = 16, className = "", ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      role="img"
      aria-label={rest["aria-label"] ?? "足球"}
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M12 4.5 L15.5 7.5 L14 12 L10 12 L8.5 7.5 Z" fill="currentColor" stroke="none" />
      <path d="M15.5 7.5 L20 9.5 M14 12 L17 16 M10 12 L7 16 M8.5 7.5 L4 9.5" />
    </svg>
  );
}

function MedalGold({ size = 16, className = "" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} role="img" aria-label="奖牌">
      <defs>
        <linearGradient id="gold-grad" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#fde047" />
          <stop offset="100%" stopColor="#ca8a04" />
        </linearGradient>
      </defs>
      <path d="M8 2 L10 8 L14 8 L16 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="12" cy="15" r="6" fill="url(#gold-grad)" stroke="#a16207" strokeWidth="0.5" />
      <text x="12" y="18" textAnchor="middle" fontSize="6" fontWeight="700" fill="#7c2d12">1</text>
    </svg>
  );
}

function ChartUp({ size = 16, className = "" }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      role="img"
      aria-label="增长趋势"
    >
      <path d="M3 17 L9 11 L13 15 L21 7" />
      <path d="M17 7 L21 7 L21 11" />
    </svg>
  );
}

function ProbabilityDot({ size = 16, className = "" }: IconProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" className={className} role="img" aria-label="概率指示">
      <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="2" />
      <circle cx="12" cy="12" r="4" fill="currentColor" />
    </svg>
  );
}

function HotStreak({ size = 16, className = "" }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      role="img"
      aria-label="热门"
    >
      <path d="M12 22 C7 22 4 18 4 14 C4 11 6 9 7 8 C7 10 8 11 9 11 C9 8 11 5 12 2 C13 5 15 8 17 11 C18 11 19 10 19 8 C20 9 20 11 20 14 C20 18 17 22 12 22 Z" />
    </svg>
  );
}

/* ─── Registry ───────────────────────────────────────────────────────────── */

export const IconRegistry = {
  // Status & feedback
  success: CheckCircle2,
  error: XCircle,
  warn: AlertTriangle,
  info: Info,
  help: CircleHelp,
  alert: AlertCircle,
  pending: Clock,
  loading: Loader,
  hourglass: Hourglass,

  // Navigation
  back: ArrowLeft,
  forward: ArrowRight,
  up: ArrowUp,
  down: ArrowDown,
  chevronUp: ChevronUp,
  chevronDown: ChevronDown,
  chevronLeft: ChevronLeft,
  chevronRight: ChevronRight,
  more: MoreHorizontal,
  menu: Menu,
  close: X,

  // Actions
  refresh: RefreshCw,
  filter: Filter,
  search: Search,
  settings: Settings,
  settingsAlt: Settings2,
  lock: Lock,
  unlock: Unlock,

  // Theme
  moon: Moon,
  sun: Sun,
  weather: CloudSun,

  // Data & analytics
  chart: BarChart3,
  chartUp: ChartUp,
  trendUp: TrendingUp,
  trendDown: TrendingDown,
  database: Database,
  gauge: Gauge,
  target: Target,
  probability: ProbabilityDot,

  // Dashboard sections
  overview: Target,
  production: Rocket,
  model: Gauge,
  signals: TrendingUp,
  data: Database,

  // Domain (football)
  football: Football,
  shield: ShieldCheck,
  trophy: Trophy,
  medal: MedalGold,
  flag: Flag,
  team: UsersRound,
  player: UserRound,
  hot: HotStreak,

  // Time / venue
  calendar: Calendar,
  clock: Clock,
  history: History,
  location: MapPin,

  // System
  brain: BrainCircuit,
  activity: Activity,
  eye: Eye,
  checklist: ListChecks,
  sparkles: Sparkles,
  star: Star,
  zap: Zap,
  shieldCheck: ShieldCheck,
  circleCheck: CircleCheck,
} as const;

export type IconName = keyof typeof IconRegistry;

type Props = {
  name: IconName;
  size?: number;
  className?: string;
  strokeWidth?: number;
  "aria-label"?: string;
};

/**
 * Render an icon by name. This is the recommended way to use icons throughout
 * the dashboard — never import lucide-react directly in feature components.
 */
export function Icon({ name, size = 16, className = "", strokeWidth, ...rest }: Props) {
  const Component = IconRegistry[name] as LucideIcon | ((p: IconProps) => ReactElement);
  if (!Component) return null;
  // Lucide accepts strokeWidth, our custom icons accept arbitrary props
  const props: any = { size, className, "aria-label": rest["aria-label"] };
  if (strokeWidth !== undefined) props.strokeWidth = strokeWidth;
  return <Component {...props} />;
}

/**
 * Compact wrapper that auto-applies a circular tinted background — useful
 * for hero cards and metric labels.
 */
export function IconChip({
  name,
  size = 14,
  tone = "neutral",
  className = "",
}: {
  name: IconName;
  size?: number;
  tone?: "neutral" | "brand" | "strike" | "success" | "danger" | "warning" | "info";
  className?: string;
}) {
  const toneClasses: Record<string, string> = {
    neutral: "bg-ink-100 dark:bg-ink-800 text-ink-700 dark:text-ink-300",
    brand:   "bg-brand-50 dark:bg-brand-900/40 text-brand-600 dark:text-brand-400",
    strike:  "bg-strike-50 dark:bg-strike-900/40 text-strike-600 dark:text-strike-400",
    success: "bg-success-500/10 text-success-600 dark:text-success-500",
    danger:  "bg-danger-500/10 text-danger-600 dark:text-danger-500",
    warning: "bg-warning-500/10 text-warning-600 dark:text-warning-500",
    info:    "bg-info-500/10 text-info-600 dark:text-info-500",
  };
  return (
    <span className={`inline-flex items-center justify-center rounded-lg p-1.5 ${toneClasses[tone]} ${className}`}>
      <Icon name={name} size={size} />
    </span>
  );
}
