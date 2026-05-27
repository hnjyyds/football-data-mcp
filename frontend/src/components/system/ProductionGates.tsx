import { Icon } from "../shared/Icon";
import { Badge, toneVariant } from "../shared/Badge";

type Gate = {
  name: string;
  status: string;
  tone?: string;
  detail?: string;
  required?: boolean;
};

function GateIcon({ tone }: { tone: string | undefined }) {
  if (tone === "good") return <Icon name="success" size={14} className="text-success-500" />;
  if (tone === "bad") return <Icon name="error" size={14} className="text-danger-500" />;
  if (tone === "caution") return <Icon name="warn" size={14} className="text-warning-500" />;
  return <Icon name="warn" size={14} className="text-ink-400" />;
}

export function ProductionGates({
  gates,
  overallTone,
  overallLabel,
}: {
  gates: Gate[];
  overallTone: string;
  overallLabel: string;
}) {
  const isReady = overallTone === "good";
  return (
    <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-3 border-b border-slate-100 dark:border-slate-700/50">
        <Icon name={isReady ? "unlock" : "lock"} size={16} className={isReady ? "text-success-500" : "text-warning-500"} />
        <span className="font-semibold text-slate-900 dark:text-white text-sm flex-1">上线门控</span>
        <Badge variant={toneVariant(overallTone)}>{overallLabel}</Badge>
      </div>
      <div className="divide-y divide-slate-50 dark:divide-slate-700/30">
        {gates.map((gate) => (
          <div key={gate.name} className="flex items-start gap-3 px-4 py-2.5">
            <GateIcon tone={gate.tone} />
            <div className="flex-1 min-w-0">
              <div className="text-xs font-medium text-slate-800 dark:text-slate-200">{gate.name}</div>
              {gate.detail && <div className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">{gate.detail}</div>}
            </div>
            {gate.required && (
              <span className="text-xs text-slate-400 dark:text-slate-500 flex-shrink-0">必须</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
