import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useState } from "react";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState, Spinner } from "@/components/ui/feedback";
import { Select, Textarea, Field } from "@/components/ui/form";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import type { Application, Check, ProviderCall } from "@/lib/types";
import { dateTime, titleCase } from "@/lib/utils";

const categories = ["KYC", "AML", "FRAUD"];

function renderValue(value: unknown): React.ReactNode {
  if (Array.isArray(value)) {
    return (
      <ul className="mt-1 list-disc space-y-1 pl-4">
        {value.map((item, i) => <li key={i}>{typeof item === "object" && item !== null && "text" in item ? String((item as { text: unknown }).text) : typeof item === "object" ? JSON.stringify(item) : String(item)}</li>)}
      </ul>
    );
  }
  if (typeof value === "object" && value !== null) return JSON.stringify(value);
  return String(value);
}

function Evidence({ value }: { value: Record<string, unknown> }) {
  const entries = Object.entries(value).filter(([, v]) => !(Array.isArray(v) && v.length === 0) && v !== null && v !== "");
  if (entries.length === 0) return null;
  return (
    <dl className="mt-2 space-y-1 text-xs text-muted">
      {entries.map(([k, v]) => <div key={k} className="min-w-0"><dt className="inline font-medium text-ink">{titleCase(k)}: </dt><dd className={Array.isArray(v) ? "block" : "inline break-words"}>{renderValue(v)}</dd></div>)}
    </dl>
  );
}

function Disposition({ check, application, onClose }: { check: Check; application: Application; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [disposition, setDisposition] = useState("CLEARED");
  const [note, setNote] = useState("");
  const save = useMutation({
    mutationFn: () => api(`/applications/${application.id}/verification/${check.id}/disposition`, { body: { disposition, note } }),
    onSuccess: () => { toast.success("Disposition recorded"); queryClient.invalidateQueries(); onClose(); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()} title={`Disposition: ${check.title}`} description={check.detail}>
      <div className="space-y-4">
        <Field label="Outcome of your review">
          <Select value={disposition} onChange={(e) => setDisposition(e.target.value)}>
            <option value="CLEARED">Cleared. The concern is not supported</option>
            <option value="CONFIRMED">Confirmed. The concern stands</option>
          </Select>
        </Field>
        <Field label="Note" hint="At least 10 characters. It goes into the audit trail."><Textarea value={note} onChange={(e) => setNote(e.target.value)} /></Field>
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button disabled={note.trim().length < 10} loading={save.isPending} onClick={() => save.mutate()}>Record disposition</Button>
        </div>
      </div>
    </Dialog>
  );
}

export function VerificationTab({ application, canReview }: { application: Application; canReview: boolean }) {
  const checks = useQuery({ queryKey: ["verification", application.id], queryFn: () => api<Check[]>(`/applications/${application.id}/verification`) });
  const calls = useQuery({ queryKey: ["provider-calls", application.id], queryFn: () => api<ProviderCall[]>(`/applications/${application.id}/provider-calls`) });
  const [target, setTarget] = useState<Check | null>(null);
  const [open, setOpen] = useState<number | null>(null);
  const people = new Map(application.applicants.map((a) => [a.id, a.full_name]));
  if (checks.isLoading || calls.isLoading) return <Spinner />;
  const list = checks.data ?? [];
  return (
    <div className="space-y-6">
      {list.length === 0 && <Card><EmptyState title="Verification has not run" description="Checks appear here once the application has been submitted and processed." /></Card>}
      {categories.map((category) => {
        const items = list.filter((c) => c.category === category);
        if (items.length === 0) return null;
        return (
          <Card key={category}>
            <CardHeader title={category === "KYC" ? "KYC" : category === "AML" ? "AML screening" : "Fraud indicators"} description={category === "FRAUD" ? "Indicators from document analysis and cross checks. They are not proof of fraud and need a person to review." : undefined} />
            <ul>
              {items.map((c) => (
                <li key={c.id} className="border-b border-line px-5 py-4 last:border-b-0">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium">{c.title} {c.applicant_id && <span className="font-normal text-muted">· {people.get(c.applicant_id)}</span>}</p>
                      <p className="mt-0.5 text-sm text-muted">{c.detail}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      {c.disposition && <Badge tone={c.disposition === "CLEARED" ? "ok" : "bad"}>{titleCase(c.disposition)}</Badge>}
                      <StatusBadge status={c.status} />
                      {canReview && (c.status === "FLAG" || c.status === "REFER") && !c.disposition && application.status === "REFERRED" && <Button size="sm" variant="outline" onClick={() => setTarget(c)}>Disposition</Button>}
                    </div>
                  </div>
                  {c.disposition_note && <p className="mt-2 rounded-md bg-brand-tint p-2 text-xs">Reviewer note: {c.disposition_note}</p>}
                  <Evidence value={c.evidence} />
                </li>
              ))}
            </ul>
          </Card>
        );
      })}
      <Card>
        <CardHeader title="Provider calls" description="Each call is labelled with its mode. Nothing here is a live partner response." />
        {(calls.data ?? []).length === 0 ? <EmptyState title="No provider calls yet" /> : (
          <Table>
            <thead><tr><Th>Source</Th><Th>Mode</Th><Th>Response</Th><Th>Result</Th><Th>Consent ref</Th><Th>When</Th><Th /></tr></thead>
            <tbody>
              {calls.data!.map((c) => (
                <Fragment key={c.id}>
                  <Tr>
                    <Td className="font-medium">{c.provider_name}{c.applicant_id && <div className="text-xs font-normal text-muted">{people.get(c.applicant_id)}</div>}</Td>
                    <Td><StatusBadge status={c.mode} /></Td>
                    <Td><StatusBadge status={c.response_status} /></Td>
                    <Td><StatusBadge status={c.verification_result} /></Td>
                    <Td className="font-mono text-xs">{c.consent_ref ?? "-"}</Td>
                    <Td className="whitespace-nowrap">{dateTime(c.requested_at)}</Td>
                    <Td><Button variant="ghost" size="sm" onClick={() => setOpen(open === c.id ? null : c.id)}>{open === c.id ? "Hide" : "Details"}</Button></Td>
                  </Tr>
                  {open === c.id && <tr><td colSpan={7} className="border-b border-line bg-brand-tint px-4 py-3"><pre className="overflow-x-auto whitespace-pre-wrap text-xs">{JSON.stringify(c.response, null, 2)}</pre></td></tr>}
                </Fragment>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      {target && <Disposition check={target} application={application} onClose={() => setTarget(null)} />}
    </div>
  );
}
