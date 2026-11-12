import { useQuery } from "@tanstack/react-query";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorNotice, KeyValue, Spinner, Stat } from "@/components/ui/feedback";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { api, ApiError, errorMessage } from "@/lib/api";
import { inr, pct, titleCase } from "@/lib/utils";

interface Financial {
  financial: {
    inputs: Record<string, number>;
    formulas: Record<string, string>;
    proposed_emi: number;
    foir: number;
    foir_limit: number;
    total_exposure: number;
    ltv: number;
    ltv_limit: number;
    max_eligible_emi: number;
    loan_by_foir: number;
    loan_by_ltv: number;
    indicative_eligible_loan: number;
  };
  income: {
    applicant_id: number;
    name: string;
    employment_type: string;
    candidates: Record<string, number>;
    basis: string;
    eligible_income: number;
    declared_income: number;
    variance_pct: number;
    other_income_declared: number;
    other_income_recognised: number;
    existing_emi_declared: number;
    existing_emi_bureau: number | null;
    existing_emi_used: number;
    notes: string[];
  }[];
}

export function FinancialTab({ applicationId }: { applicationId: number }) {
  const data = useQuery({ queryKey: ["financial", applicationId], queryFn: () => api<Financial>(`/applications/${applicationId}/financial`), retry: false });
  if (data.isLoading) return <Spinner />;
  if (data.error instanceof ApiError && data.error.status === 404) return <Card><EmptyState title="Not assessed yet" description="The financial assessment is calculated once documents and verification are in." /></Card>;
  if (data.isError || !data.data) return <ErrorNotice message={errorMessage(data.error)} onRetry={() => data.refetch()} />;
  const f = data.data.financial;
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="Affordability" description="Calculated by the deterministic financial engine from verified inputs." />
        <CardBody className="grid grid-cols-2 gap-6 md:grid-cols-4">
          <Stat label="Proposed EMI" value={inr(f.proposed_emi)} />
          <Stat label="FOIR" value={pct(f.foir)} tone={f.foir <= f.foir_limit ? "ok" : "bad"} hint={`Limit ${pct(f.foir_limit, 0)}`} />
          <Stat label="LTV" value={pct(f.ltv)} tone={f.ltv <= f.ltv_limit ? "ok" : "bad"} hint={`Limit ${pct(f.ltv_limit, 0)}`} />
          <Stat label="Indicative eligible loan" value={inr(f.indicative_eligible_loan, true)} hint="Lower of FOIR and LTV limits" />
        </CardBody>
      </Card>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Inputs used" />
          <CardBody>
            <KeyValue items={[
              ["Loan amount", inr(f.inputs.loan_amount)], ["Interest rate", `${f.inputs.interest_rate}% a year`], ["Tenure", `${f.inputs.tenure_months} months`],
              ["Eligible monthly income", inr(f.inputs.eligible_monthly_income)], ["Existing monthly EMI", inr(f.inputs.existing_monthly_emi)],
              ["Accepted property value", inr(f.inputs.accepted_property_value)], ["Existing mortgage on property", inr(f.inputs.existing_mortgage_amount)], ["Total exposure", inr(f.total_exposure)],
            ]} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Formulas" />
          <CardBody className="space-y-3 text-sm">
            {Object.entries(f.formulas).map(([k, v]) => <div key={k}><p className="label-sm">{k.toUpperCase()}</p><p className="font-mono text-xs">{v}</p></div>)}
            <KeyValue items={[["Maximum affordable EMI", inr(f.max_eligible_emi)], ["Loan supported by FOIR", inr(f.loan_by_foir)], ["Loan supported by LTV", inr(f.loan_by_ltv)]]} />
          </CardBody>
        </Card>
      </div>
      <Card>
        <CardHeader title="Income assessment" description="The lowest documented figure is used when sources disagree. Declared income is never taken on its own." />
        <Table>
          <thead><tr><Th>Applicant</Th><Th>Declared</Th><Th>Documented sources</Th><Th>Basis</Th><Th>Eligible income</Th><Th>Variance</Th><Th>EMI used</Th></tr></thead>
          <tbody>
            {data.data.income.map((i) => (
              <Tr key={i.applicant_id}>
                <Td className="font-medium">{i.name}<div className="text-xs font-normal text-muted">{titleCase(i.employment_type)}</div></Td>
                <Td>{inr(i.declared_income)}</Td>
                <Td className="text-xs">{Object.entries(i.candidates).map(([k, v]) => <div key={k}>{titleCase(k)}: {inr(v)}</div>)}</Td>
                <Td>{titleCase(i.basis)}</Td>
                <Td className="font-medium">{inr(i.eligible_income)}</Td>
                <Td>{pct(i.variance_pct)}</Td>
                <Td>{inr(i.existing_emi_used)}<div className="text-xs text-muted">Declared {inr(i.existing_emi_declared)}{i.existing_emi_bureau !== null ? `, bureau ${inr(i.existing_emi_bureau)}` : ""}</div></Td>
              </Tr>
            ))}
          </tbody>
        </Table>
        {data.data.income.some((i) => i.notes.length > 0) && <ul className="border-t border-line px-5 py-3 text-xs text-muted">{data.data.income.flatMap((i) => i.notes.map((n) => <li key={i.applicant_id + n}>{i.name}: {n}</li>))}</ul>}
      </Card>
    </div>
  );
}
