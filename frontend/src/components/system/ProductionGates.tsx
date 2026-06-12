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
  if (tone === "good") return <Icon name="success" size={14} className="text-success-600" />;
  if (tone === "bad") return <Icon name="error" size={14} className="text-danger-600" />;
  if (tone === "caution") return <Icon name="warn" size={14} className="text-warning-600" />;
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
    <div className="surface-panel overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 px-4 py-4">
        <div className="min-w-0">
          <div className="section-kicker">Release Gates</div>
          <div className="mt-1 flex items-center gap-2">
            <Icon name={isReady ? "unlock" : "lock"} size={16} className={isReady ? "text-success-600" : "text-warning-600"} />
            <h2 className="text-base font-semibold tracking-tight text-ink-950 dark:text-white">上线门控</h2>
          </div>
        </div>
        <Badge variant={toneVariant(overallTone)}>{overallLabel}</Badge>
      </div>
      <div className="px-4 pb-4">
        <div className="grid gap-2">
        {gates.map((gate) => (
          <div key={gate.name} className="clean-card px-3 py-3">
            <div className="flex items-start gap-3">
              <div className="mt-0.5 grid h-6 w-6 flex-shrink-0 place-items-center rounded-full bg-black/[0.035] dark:bg-white/[0.06]">
                <GateIcon tone={gate.tone} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <div className="text-sm font-semibold text-ink-900 dark:text-ink-100">{gate.name}</div>
                  {gate.required && (
                    <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-ink-400 dark:text-ink-500">必须</span>
                  )}
                </div>
                {gate.detail && <div className="mt-1 text-xs leading-relaxed text-ink-500 dark:text-ink-400">{gate.detail}</div>}
              </div>
              <Badge variant={toneVariant(gate.tone)} className="flex-shrink-0">{gate.status}</Badge>
            </div>
          </div>
        ))}
        </div>
      </div>
    </div>
  );
}
