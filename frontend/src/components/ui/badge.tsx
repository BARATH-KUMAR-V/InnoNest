import { cn, titleCase } from "@/lib/utils";

const tones = {
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  info: "bg-info-soft text-info",
  neutral: "bg-[#ECEDE6] text-muted",
};

export type Tone = keyof typeof tones;

const statusTone: Record<string, Tone> = {
  APPROVED: "ok", APPROVE: "ok", PASS: "ok", VERIFIED: "ok", SATISFIED: "ok", FULFILLED: "ok", DELIVERED: "ok", EXTRACTED: "ok", ACTIVE: "ok", OK: "ok", CLEARED: "ok",
  REJECTED: "bad", REJECT: "bad", FAIL: "bad", FAILED: "bad", EXPIRED: "bad", UNREADABLE: "bad", MISMATCH: "bad", INTEGRITY_INDICATOR: "bad", UNAVAILABLE: "bad", CONSENT_MISSING: "bad",
  REFERRED: "warn", REFER: "warn", FLAG: "warn", FLAGGED: "warn", ACTION_REQUIRED: "warn", OPEN: "warn", NEEDS_REVIEW: "warn", PARTIAL: "warn", POTENTIAL_MATCH: "warn", EXPLAINED: "warn", NOT_CONFIGURED: "warn",
  SUBMITTED: "info", PROCESSING: "info", DOCUMENTS_RECEIVED: "info", VERIFICATION_PENDING: "info", RESPONDED: "info", SIMULATED_NOT_SENT: "info", MOCK: "info", SANDBOX: "info",
  DRAFT: "neutral", WITHDRAWN: "neutral", NOT_CHECKED: "neutral", SUPERSEDED: "neutral", ARCHIVED: "neutral", LIVE_PARTNER: "ok",
};

export function Badge({ tone = "neutral", className, children }: { tone?: Tone; className?: string; children: React.ReactNode }) {
  return <span className={cn("inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium", tones[tone], className)}>{children}</span>;
}

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  return (
    <Badge tone={statusTone[status] ?? "neutral"} className={className}>
      {titleCase(status)}
    </Badge>
  );
}
