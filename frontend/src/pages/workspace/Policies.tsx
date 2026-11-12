import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { History } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/Layout";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { ErrorNotice, Spinner } from "@/components/ui/feedback";
import { Field, Input, Textarea } from "@/components/ui/form";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { useTitle } from "@/hooks/useTitle";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Policy } from "@/lib/types";
import { dateTime, inr, titleCase } from "@/lib/utils";

type Band = [number | null, number];

interface Draft {
  foir: Record<string, string>;
  ltvHome: string[];
  ltvLap: string;
  creditReject: string;
  creditRefer: string;
  riskReject: string;
  riskRefer: string;
  incomeVariance: string;
  valuationDeviation: string;
  otherIncome: string;
  fraudScore: string;
  maxDpd: string;
  minIncomeHome: string;
  minIncomeLap: string;
}

const percent = (v: number) => String(Math.round(v * 10000) / 100);
const fraction = (v: string) => Number(v) / 100;

function toDraft(p: Policy["params"]): Draft {
  return {
    foir: Object.fromEntries(Object.entries(p.foir_limit as Record<string, number>).map(([k, v]) => [k, percent(v)])),
    ltvHome: (p.ltv_limit.HOME_LOAN as Band[]).map((b) => percent(b[1])),
    ltvLap: percent((p.ltv_limit.LAP as Band[])[0][1]),
    creditReject: String(p.credit_score.reject_below),
    creditRefer: String(p.credit_score.refer_below),
    riskReject: String(p.risk_score.reject_below),
    riskRefer: String(p.risk_score.refer_below),
    incomeVariance: percent(p.income_variance_refer_pct),
    valuationDeviation: percent(p.valuation_deviation_refer_pct),
    otherIncome: percent(p.other_income_recognition),
    fraudScore: String(p.fraud_refer_score),
    maxDpd: String(p.max_dpd_12m),
    minIncomeHome: String(p.min_monthly_income.HOME_LOAN),
    minIncomeLap: String(p.min_monthly_income.LAP),
  };
}

function toParams(d: Draft, base: Policy["params"]): Policy["params"] {
  const home = (base.ltv_limit.HOME_LOAN as Band[]).map((b, i) => [b[0], fraction(d.ltvHome[i])] as Band);
  const lapBase = (base.ltv_limit.LAP as Band[])[0];
  return {
    foir_limit: Object.fromEntries(Object.entries(d.foir).map(([k, v]) => [k, fraction(v)])),
    ltv_limit: { HOME_LOAN: home, LAP: [[lapBase[0], fraction(d.ltvLap)]] },
    credit_score: { reject_below: Number(d.creditReject), refer_below: Number(d.creditRefer) },
    risk_score: { reject_below: Number(d.riskReject), refer_below: Number(d.riskRefer) },
    income_variance_refer_pct: fraction(d.incomeVariance),
    valuation_deviation_refer_pct: fraction(d.valuationDeviation),
    other_income_recognition: fraction(d.otherIncome),
    fraud_refer_score: Number(d.fraudScore),
    max_dpd_12m: Number(d.maxDpd),
    min_monthly_income: { HOME_LOAN: Number(d.minIncomeHome), LAP: Number(d.minIncomeLap) },
  };
}

function bandLabel(bands: Band[], index: number): string {
  const upper = bands[index][0];
  const lower = index === 0 ? 0 : (bands[index - 1][0] as number);
  return upper === null ? `above ${inr(lower, true)}` : `up to ${inr(upper, true)}`;
}

function Editor({ policy, onClose }: { policy: Policy; onClose: () => void }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<Draft>(() => toDraft(policy.params));
  const [note, setNote] = useState("");
  const bands = policy.params.ltv_limit.HOME_LOAN as Band[];
  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));
  const save = useMutation({
    mutationFn: () => api<Policy>(`/policies/${policy.key}`, { method: "PUT", body: { params: toParams(draft, policy.params), change_note: note } }),
    onSuccess: (saved) => {
      toast.success(`${saved.name} policy version ${saved.version} published`);
      queryClient.invalidateQueries({ queryKey: ["policies"] });
      onClose();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const field = (label: string, value: string, onChange: (v: string) => void, hint?: string) => (
    <Field label={label} hint={hint}><Input type="number" step="any" value={value} onChange={(e) => onChange(e.target.value)} /></Field>
  );
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted">Saving publishes a new version. Earlier decisions keep the version they were made under and can still be replayed.</p>
      <section>
        <h3 className="section-title mb-3">FOIR limit by employment (%)</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          {Object.entries(draft.foir).map(([key, value]) => <div key={key}>{field(titleCase(key), value, (v) => set({ foir: { ...draft.foir, [key]: v } }))}</div>)}
        </div>
      </section>
      <section>
        <h3 className="section-title mb-3">LTV limit (%)</h3>
        <div className="grid gap-4 sm:grid-cols-4">
          {bands.map((_, i) => <div key={i}>{field(`Home loan ${bandLabel(bands, i)}`, draft.ltvHome[i], (v) => set({ ltvHome: draft.ltvHome.map((x, j) => (j === i ? v : x)) }))}</div>)}
          {field("Loan against property", draft.ltvLap, (v) => set({ ltvLap: v }))}
        </div>
      </section>
      <section>
        <h3 className="section-title mb-3">Credit and risk thresholds</h3>
        <div className="grid gap-4 sm:grid-cols-4">
          {field("Reject below bureau score", draft.creditReject, (v) => set({ creditReject: v }))}
          {field("Refer below bureau score", draft.creditRefer, (v) => set({ creditRefer: v }))}
          {field("Reject below risk score", draft.riskReject, (v) => set({ riskReject: v }))}
          {field("Refer below risk score", draft.riskRefer, (v) => set({ riskRefer: v }))}
          {field("Maximum days past due, 12 months", draft.maxDpd, (v) => set({ maxDpd: v }))}
          {field("Fraud score that refers", draft.fraudScore, (v) => set({ fraudScore: v }), "Between 0 and 1")}
        </div>
      </section>
      <section>
        <h3 className="section-title mb-3">Income and valuation</h3>
        <div className="grid gap-4 sm:grid-cols-3">
          {field("Minimum income, home loan (INR)", draft.minIncomeHome, (v) => set({ minIncomeHome: v }))}
          {field("Minimum income, LAP (INR)", draft.minIncomeLap, (v) => set({ minIncomeLap: v }))}
          {field("Other income recognised (%)", draft.otherIncome, (v) => set({ otherIncome: v }))}
          {field("Income variance that refers (%)", draft.incomeVariance, (v) => set({ incomeVariance: v }))}
          {field("Valuation deviation that refers (%)", draft.valuationDeviation, (v) => set({ valuationDeviation: v }))}
        </div>
      </section>
      <Field label="Reason for this change" hint="At least 10 characters. It is kept in the version history and the audit trail.">
        <Textarea value={note} onChange={(e) => setNote(e.target.value)} />
      </Field>
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button disabled={note.trim().length < 10} loading={save.isPending} onClick={() => save.mutate()}>Publish new version</Button>
      </div>
    </div>
  );
}

function PolicyHistory({ policyKey }: { policyKey: string }) {
  const history = useQuery({ queryKey: ["policies", "history", policyKey], queryFn: () => api<Policy[]>(`/policies/${policyKey}/history`) });
  if (history.isLoading) return <Spinner />;
  return (
    <Table>
      <thead><tr><Th>Version</Th><Th>Status</Th><Th>Published</Th><Th>By</Th><Th>Change note</Th></tr></thead>
      <tbody>
        {(history.data ?? []).map((p) => (
          <Tr key={p.id}><Td>v{p.version}</Td><Td><StatusBadge status={p.status} /></Td><Td>{dateTime(p.created_at)}</Td><Td>{p.created_by}</Td><Td className="text-muted">{p.change_note ?? "Initial illustrative policy"}</Td></Tr>
        ))}
      </tbody>
    </Table>
  );
}

function Summary({ policy }: { policy: Policy }) {
  const p = policy.params;
  const rows: [string, string][] = [
    ["FOIR limit", Object.entries(p.foir_limit as Record<string, number>).map(([k, v]) => `${titleCase(k)} ${percent(v)}%`).join(", ")],
    ["LTV, home loan", (p.ltv_limit.HOME_LOAN as Band[]).map((b, i, all) => `${bandLabel(all, i)} ${percent(b[1])}%`).join(", ")],
    ["LTV, LAP", `${percent((p.ltv_limit.LAP as Band[])[0][1])}%`],
    ["Bureau score", `Reject below ${p.credit_score.reject_below}, refer below ${p.credit_score.refer_below}`],
    ["Risk score", `Reject below ${p.risk_score.reject_below}, refer below ${p.risk_score.refer_below}`],
    ["Days past due allowed", `${p.max_dpd_12m} in the last 12 months`],
    ["Other income recognised", `${percent(p.other_income_recognition)}%`],
    ["Income variance that refers", `${percent(p.income_variance_refer_pct)}%`],
    ["Valuation deviation that refers", `${percent(p.valuation_deviation_refer_pct)}%`],
    ["Minimum income", `Home loan ${inr(p.min_monthly_income.HOME_LOAN)}, LAP ${inr(p.min_monthly_income.LAP)}`],
    ["Not accepted", `${(p.disallowed_property_types.HOME_LOAN as string[]).map(titleCase).join(", ")} property; ${(p.disallowed_end_uses as string[]).map(titleCase).join(", ")} end use`],
  ];
  return (
    <dl className="grid gap-x-8 gap-y-3 sm:grid-cols-2">
      {rows.map(([k, v]) => <div key={k}><dt className="label-sm">{k}</dt><dd className="mt-0.5 text-sm">{v}</dd></div>)}
    </dl>
  );
}

export default function Policies() {
  useTitle("Policy configuration");
  const { user } = useAuth();
  const canEdit = user?.role === "policy_admin";
  const list = useQuery({ queryKey: ["policies"], queryFn: () => api<Policy[]>("/policies") });
  const [editing, setEditing] = useState<Policy | null>(null);
  const [tab, setTab] = useState("balanced");
  useEffect(() => {
    if (list.data && !list.data.some((p) => p.key === tab)) setTab(list.data[0]?.key ?? "balanced");
  }, [list.data, tab]);
  if (list.isLoading) return <Spinner />;
  if (list.isError || !list.data) return <ErrorNotice message={errorMessage(list.error)} onRetry={() => list.refetch()} />;
  return (
    <div className="space-y-6">
      <PageHeader title="Policy configuration" description="Three illustrative lender policies. They are not any real lender's rules. Every change creates a new version." />
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>{list.data.map((p) => <TabsTrigger key={p.key} value={p.key}>{p.name}</TabsTrigger>)}</TabsList>
        {list.data.map((p) => (
          <TabsContent key={p.key} value={p.key} className="space-y-6">
            <Card>
              <CardHeader
                title={`${p.name} policy`}
                description={p.description}
                action={<div className="flex items-center gap-2"><Badge tone="info">Version {p.version}</Badge>{canEdit && <Button size="sm" onClick={() => setEditing(p)}>Edit</Button>}</div>}
              />
              <CardBody><Summary policy={p} /></CardBody>
            </Card>
            <Card>
              <CardHeader title="Version history" action={<History className="h-4 w-4 text-muted" />} />
              <PolicyHistory policyKey={p.key} />
            </Card>
          </TabsContent>
        ))}
      </Tabs>
      {!canEdit && <p className="text-xs text-muted">Only a policy administrator can publish a new version.</p>}
      <Dialog open={editing !== null} onOpenChange={(o) => !o && setEditing(null)} title={editing ? `Edit ${editing.name} policy` : ""} wide>
        {editing && <Editor key={editing.id} policy={editing} onClose={() => setEditing(null)} />}
      </Dialog>
    </div>
  );
}
