import { Check } from "lucide-react";
import { cn, titleCase } from "@/lib/utils";

const stages = ["Draft", "Submitted", "Under review", "Decision"];

function position(status: string): number {
  if (status === "DRAFT") return 0;
  if (status === "SUBMITTED") return 1;
  if (["PROCESSING", "ACTION_REQUIRED", "DOCUMENTS_RECEIVED", "VERIFICATION_PENDING", "REFERRED"].includes(status)) return 2;
  return 3;
}

export function StatusStepper({ status }: { status: string }) {
  const current = position(status);
  const closed = ["APPROVED", "REJECTED", "EXPIRED", "WITHDRAWN"].includes(status);
  return (
    <ol className="grid grid-cols-4 gap-2" aria-label="Application progress">
      {stages.map((stage, index) => {
        const done = index < current || (index === current && closed);
        const active = index === current && !closed;
        return (
          <li key={stage} className="min-w-0">
            <div className={cn("h-1.5 rounded-full", done || active ? "bg-brand" : "bg-line")} />
            <div className="mt-2 flex items-center gap-1.5 text-xs">
              <span className={cn("flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-[10px]", done ? "bg-brand text-white" : active ? "border-2 border-brand text-brand" : "border border-line text-muted")}>
                {done ? <Check className="h-3 w-3" /> : index + 1}
              </span>
              <span className={cn("truncate font-medium", active || done ? "text-ink" : "text-muted")}>{index === 3 && closed ? titleCase(status) : stage}</span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
