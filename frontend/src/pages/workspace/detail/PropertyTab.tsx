import { useQuery } from "@tanstack/react-query";
import { StatusBadge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorNotice, KeyValue, Spinner } from "@/components/ui/feedback";
import { api, ApiError, errorMessage } from "@/lib/api";
import { inr, pct, titleCase } from "@/lib/utils";

interface Property {
  checks: { code: string; title: string; status: string; detail: string; evidence: Record<string, unknown> }[];
  declared_value: number;
  valuation_value: number | null;
  accepted_value: number;
  deviation_pct: number | null;
  existing_mortgage_amount: number;
  legal_title_note: string;
}

export function PropertyTab({ applicationId }: { applicationId: number }) {
  const data = useQuery({ queryKey: ["property", applicationId], queryFn: () => api<Property>(`/applications/${applicationId}/property`), retry: false });
  if (data.isLoading) return <Spinner />;
  if (data.error instanceof ApiError && data.error.status === 404) return <Card><EmptyState title="Not assessed yet" description="The property assessment runs once the property documents are in." /></Card>;
  if (data.isError || !data.data) return <ErrorNotice message={errorMessage(data.error)} onRetry={() => data.refetch()} />;
  const p = data.data;
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Valuation" />
        <CardBody>
          <KeyValue items={[
            ["Declared value", inr(p.declared_value)], ["Valuation report", inr(p.valuation_value)], ["Value accepted for LTV", inr(p.accepted_value)],
            ["Valuation against declared", p.deviation_pct === null ? "-" : pct(p.deviation_pct)], ["Existing mortgage", inr(p.existing_mortgage_amount)],
          ]} />
          <p className="mt-4 rounded-md bg-info-soft p-3 text-xs text-info">{p.legal_title_note}</p>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Property checks" />
        <ul>
          {p.checks.map((c) => (
            <li key={c.code} className="border-b border-line px-5 py-4 last:border-b-0">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><p className="text-sm font-medium">{c.title}</p><p className="mt-0.5 text-sm text-muted">{c.detail}</p></div>
                <StatusBadge status={c.status} />
              </div>
              {Object.keys(c.evidence).length > 0 && (
                <dl className="mt-2 grid gap-x-4 gap-y-1 text-xs text-muted sm:grid-cols-2">
                  {Object.entries(c.evidence).map(([k, v]) => <div key={k}><dt className="inline font-medium text-ink">{titleCase(k)}: </dt><dd className="inline break-words">{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd></div>)}
                </dl>
              )}
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
