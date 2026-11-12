import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, RotateCcw, XCircle } from "lucide-react";
import { useState } from "react";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/dialog";
import { EmptyState, KeyValue, Spinner } from "@/components/ui/feedback";
import { Field, Select, Textarea } from "@/components/ui/form";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import type { Application, Decision } from "@/lib/types";
import { dateTime } from "@/lib/utils";

interface Replay {
  decision_id: number;
  stored_outcome: string;
  recomputed_outcome: string;
  identical: boolean;
  stored_hash: string;
  recomputed_hash: string;
  steps: { step: string; detail: string }[];
}

interface Comparison {
  outcomes: { policy_key: string; policy_name: string; policy_version: number; outcome: string; foir: number; foir_limit: number; ltv: number; ltv_limit: number; risk_score: number; risk_band: string; indicative_eligible_loan: number; explanation: string }[];
  differences: { code: string; name: string; by_policy: Record<string, { outcome: string; message: string }> }[];
}

const pctText = (v: number) => `${(v * 100).toFixed(1)}%`;

function ReplayPanel({ decision }: { decision: Decision }) {
  const [run, setRun] = useState(false);
  const replay = useQuery({ queryKey: ["replay", decision.id], queryFn: () => api<Replay>(`/decisions/${decision.id}/replay`), enabled: run });
  return (
    <Card>
      <CardHeader
        title="Replay"
        description="Recompute this decision from the stored inputs and the policy version it was made under."
        action={<Button variant="outline" size="sm" loading={replay.isFetching} onClick={() => (run ? replay.refetch() : setRun(true))}><RotateCcw className="h-4 w-4" /> Replay decision</Button>}
      />
      {replay.data && (
        <CardBody className="space-y-4">
          <div className={`flex items-center gap-2 rounded-md p-3 text-sm ${replay.data.identical ? "bg-ok-soft text-ok" : "bg-bad-soft text-bad"}`}>
            {replay.data.identical ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
            {replay.data.identical ? `The recomputed result is identical: ${replay.data.recomputed_outcome}.` : `The result differs. Stored ${replay.data.stored_outcome}, recomputed ${replay.data.recomputed_outcome}.`}
          </div>
          <ol className="space-y-2 text-sm">
            {replay.data.steps.map((s, i) => <li key={i}><span className="font-medium">{i + 1}. {s.step}.</span> <span className="text-muted">{s.detail}</span></li>)}
          </ol>
          <dl className="space-y-1 font-mono text-[11px] text-muted">
            <div><dt className="inline font-sans font-medium text-ink">Stored hash </dt><dd className="inline break-all">{replay.data.stored_hash}</dd></div>
            <div><dt className="inline font-sans font-medium text-ink">Recomputed hash </dt><dd className="inline break-all">{replay.data.recomputed_hash}</dd></div>
          </dl>
        </CardBody>
      )}
    </Card>
  );
}

function Compare({ applicationId, ready }: { applicationId: number; ready: boolean }) {
  const data = useQuery({ queryKey: ["compare", applicationId], queryFn: () => api<Comparison>(`/applications/${applicationId}/compare-policies`), enabled: ready, retry: false });
  if (!ready || data.isError) return null;
  if (data.isLoading) return <Spinner />;
  const c = data.data!;
  return (
    <Card>
      <CardHeader title="Policy comparison" description="The same application evaluated under each active policy. This does not change the decision." />
      <Table>
        <thead><tr><Th>Policy</Th><Th>Outcome</Th><Th>FOIR / limit</Th><Th>LTV / limit</Th><Th>Risk</Th><Th>Indicative eligible loan</Th></tr></thead>
        <tbody>
          {c.outcomes.map((o) => (
            <Tr key={o.policy_key}>
              <Td className="font-medium">{o.policy_name} v{o.policy_version}</Td>
              <Td><StatusBadge status={o.outcome} /></Td>
              <Td>{pctText(o.foir)} / {pctText(o.foir_limit)}</Td>
              <Td>{pctText(o.ltv)} / {pctText(o.ltv_limit)}</Td>
              <Td>{o.risk_score} ({o.risk_band})</Td>
              <Td>{new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(o.indicative_eligible_loan)}</Td>
            </Tr>
          ))}
        </tbody>
      </Table>
      {c.differences.length > 0 ? (
        <div className="border-t border-line px-5 py-4">
          <p className="label-sm mb-2">Where the policies differ</p>
          <ul className="space-y-2 text-sm">
            {c.differences.map((d) => (
              <li key={d.code}>
                <p className="font-medium">{d.name}</p>
                <p className="text-xs text-muted">{Object.entries(d.by_policy).map(([k, v]) => `${k}: ${v.outcome.toLowerCase()}`).join(", ")}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : <p className="border-t border-line px-5 py-3 text-xs text-muted">Every policy reaches the same result on every rule.</p>}
    </Card>
  );
}

function ReviewForm({ application }: { application: Application }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [outcome, setOutcome] = useState("APPROVE");
  const [note, setNote] = useState("");
  const [confirm, setConfirm] = useState(false);
  const review = useMutation({
    mutationFn: () => api(`/applications/${application.id}/review`, { body: { outcome, note } }),
    onSuccess: () => { toast.success(`Referral decided: ${outcome === "APPROVE" ? "approved" : "rejected"}`); setConfirm(false); queryClient.invalidateQueries(); },
    onError: (e) => { toast.error(errorMessage(e)); setConfirm(false); },
  });
  return (
    <Card>
      <CardHeader title="Manual review" description="This application was referred. Record your decision with the reasons. It is stored as a human decision beside the engine's referral." />
      <CardBody className="space-y-4">
        <Field label="Decision"><Select value={outcome} onChange={(e) => setOutcome(e.target.value)}><option value="APPROVE">Approve</option><option value="REJECT">Reject</option></Select></Field>
        <Field label="Reasons" hint="At least 10 characters. Mention the checks you reviewed."><Textarea value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        <Button disabled={note.trim().length < 10} onClick={() => setConfirm(true)}>Record decision</Button>
      </CardBody>
      <ConfirmDialog open={confirm} onOpenChange={setConfirm} title={`${outcome === "APPROVE" ? "Approve" : "Reject"} this application?`} description="This is final and is written to the audit trail." confirmLabel={outcome === "APPROVE" ? "Approve" : "Reject"} danger={outcome === "REJECT"} loading={review.isPending} onConfirm={() => review.mutate()} />
    </Card>
  );
}

export function DecisionTab({ application, canReview }: { application: Application; canReview: boolean }) {
  const decisions = useQuery({ queryKey: ["decisions", String(application.id)], queryFn: () => api<Decision[]>(`/applications/${application.id}/decisions`) });
  const [selected, setSelected] = useState<number | null>(null);
  if (decisions.isLoading) return <Spinner />;
  const list = decisions.data ?? [];
  if (list.length === 0) return <Card><EmptyState title="No decision yet" description="A decision is recorded once the application has been fully assessed. Applications waiting on an applicant or a source are never decided early." /></Card>;
  const current = list.find((d) => d.id === selected) ?? list[0];
  const rules = (current.outputs.rules ?? []) as { code: string; outcome: string; message: string; values: Record<string, unknown> }[];
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Decision" description={`${current.kind === "MANUAL" ? "Human decision" : "Engine decision"} by ${current.decided_by} on ${dateTime(current.created_at)}`} action={<StatusBadge status={current.outcome} />} />
        <CardBody className="space-y-4">
          <p className="text-sm">{current.explanation}</p>
          {current.review_note && <p className="rounded-md bg-brand-tint p-3 text-sm"><span className="font-medium">Reviewer reasons: </span>{current.review_note}</p>}
          {current.reason_codes.length > 0 && (
            <div>
              <p className="label-sm mb-2">Reason codes</p>
              <ul className="space-y-2">
                {current.reason_codes.map((r) => (
                  <li key={r.code} className="flex items-start gap-3 text-sm">
                    <StatusBadge status={r.outcome} />
                    <div><p className="font-medium">{r.name}</p><p className="text-xs text-muted">{r.message}</p></div>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <KeyValue items={[["Policy", `${current.policy_name} v${current.policy_version}`], ["Ruleset", current.ruleset_version], ["Result hash", <span key="h" className="break-all font-mono text-xs">{current.result_hash}</span>]]} />
          <p className="text-xs text-muted">Binding decisions come from the written rules, never from a language model. The explanation above is generated from the rule results.</p>
        </CardBody>
      </Card>
      {canReview && application.status === "REFERRED" && <ReviewForm application={application} />}
      <ReplayPanel decision={current} />
      <Card>
        <CardHeader title="Rule results" description="Every rule in the policy and what it found." />
        <Table>
          <thead><tr><Th>Rule</Th><Th>Result</Th><Th>Finding</Th></tr></thead>
          <tbody>
            {rules.map((r) => <Tr key={r.code}><Td className="font-mono text-xs">{r.code}</Td><Td><StatusBadge status={r.outcome} /></Td><Td>{r.message}</Td></Tr>)}
          </tbody>
        </Table>
      </Card>
      <Compare applicationId={application.id} ready />
      {list.length > 1 && (
        <Card>
          <CardHeader title="Decision history" />
          <Table>
            <thead><tr><Th>When</Th><Th>Outcome</Th><Th>Kind</Th><Th>Policy</Th><Th /></tr></thead>
            <tbody>
              {list.map((d) => (
                <Tr key={d.id}>
                  <Td>{dateTime(d.created_at)}</Td><Td><StatusBadge status={d.outcome} /></Td><Td>{d.kind}</Td><Td>{d.policy_name} v{d.policy_version}</Td>
                  <Td><Button variant="ghost" size="sm" disabled={d.id === current.id} onClick={() => setSelected(d.id)}>{d.id === current.id ? "Shown" : "Show"}</Button></Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        </Card>
      )}
    </div>
  );
}
