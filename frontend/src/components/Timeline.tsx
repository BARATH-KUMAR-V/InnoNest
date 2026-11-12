import { useQuery } from "@tanstack/react-query";
import { Spinner, EmptyState } from "@/components/ui/feedback";
import { api } from "@/lib/api";
import { dateTime, titleCase, docLabel } from "@/lib/utils";

interface Entry {
  id: number;
  action: string;
  actor: string;
  at: string;
  details: Record<string, any>;
}

const labels: Record<string, (d: Record<string, any>) => string> = {
  "application.submitted": () => "Application submitted",
  "application.status_changed": (d) => `Status changed to ${titleCase(d.to)}${d.reason ? `. ${d.reason}` : ""}`,
  "document.uploaded": (d) => `Document uploaded: ${docLabel(d.doc_type)} (${titleCase(d.extraction_status)})`,
  "followup.request_created": (d) => `Information requested: ${d.title}`,
  "followup.request_fulfilled": (d) => `Request ${d.status === "RESPONDED" ? "answered" : "fulfilled"}: ${titleCase(String(d.item_key).split(":")[1])}`,
  "followup.reminder_sent": (d) => `Reminder ${d.reminder_number} sent`,
  "notification.created": (d) => `Notification sent: ${d.subject}`,
  "application.clarification": () => "Clarification submitted",
  "application.updated": () => "Application details updated",
  "application.consent": () => "Consent recorded",
  "decision.recorded": (d) => `Decision recorded: ${titleCase(d.outcome)} under ${titleCase(d.policy)} policy v${d.policy_version}`,
  "decision.reviewed": (d) => `Referral reviewed: ${titleCase(d.outcome)}`,
  "application.expired": () => "Application expired",
};

export function Timeline({ applicationId }: { applicationId: number }) {
  const history = useQuery({ queryKey: ["history", applicationId], queryFn: () => api<Entry[]>(`/applications/${applicationId}/history`) });
  if (history.isLoading) return <Spinner />;
  const entries = history.data ?? [];
  if (entries.length === 0) return <EmptyState title="No activity yet" description="Events appear here as the application moves along." />;
  return (
    <ol className="relative space-y-4 border-l border-line pl-5">
      {[...entries].reverse().map((entry) => (
        <li key={entry.id} className="relative">
          <span className="absolute -left-[26px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-brand" />
          <p className="text-sm">{(labels[entry.action] ?? (() => titleCase(entry.action.replace(".", " "))))(entry.details)}</p>
          <p className="text-xs text-muted">{dateTime(entry.at)} · {entry.actor}</p>
        </li>
      ))}
    </ol>
  );
}
