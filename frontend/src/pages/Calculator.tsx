import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { z } from "zod";
import { PageHeader } from "@/components/Layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/form";
import { KeyValue, Stat } from "@/components/ui/feedback";
import { useToast } from "@/components/ui/toast";
import { useTitle } from "@/hooks/useTitle";
import { api, errorMessage } from "@/lib/api";
import { inr, pct } from "@/lib/utils";

const num = (message: string) => z.number({ invalid_type_error: message, required_error: message });

const schema = z.object({
  product: z.enum(["HOME_LOAN", "LAP"]),
  policy_key: z.enum(["balanced", "conservative", "flexible"]),
  employment_type: z.enum(["SALARIED", "GOVT", "SELF_EMPLOYED"]),
  monthly_income: num("Enter the monthly income").gt(0, "Must be above zero"),
  other_income: num("Enter 0 if none").min(0, "Cannot be negative"),
  existing_emi: num("Enter 0 if none").min(0, "Cannot be negative"),
  property_value: num("Enter the property value").gt(0, "Must be above zero"),
  interest_rate: num("Enter the rate").min(0, "Cannot be negative").max(40, "At most 40%"),
  tenure_months: num("Enter the tenure").int("Whole months only").min(1, "At least 1").max(480, "At most 480"),
  loan_amount: num("Enter the loan amount").gt(0, "Must be above zero"),
});

type Values = z.infer<typeof schema>;

interface Eligibility {
  policy: string;
  eligible_income: number;
  foir_limit: number;
  ltv_limit: number;
  max_eligible_emi: number;
  loan_by_foir: number;
  loan_by_ltv: number;
  indicative_eligible_loan: number;
  proposed_emi?: number;
  foir?: number;
  ltv?: number;
}

interface EmiResult {
  emi: number;
  total_payable: number;
  total_interest: number;
  formula: string;
  schedule_preview: { month: number; interest: number; principal: number; balance: number }[];
}

export default function Calculator() {
  useTitle("Calculator");
  const toast = useToast();
  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: { product: "HOME_LOAN", policy_key: "balanced", employment_type: "SALARIED", monthly_income: 90000, other_income: 0, existing_emi: 0, property_value: 6000000, interest_rate: 8.5, tenure_months: 240, loan_amount: 4000000 },
  });
  const { register, handleSubmit, formState: { errors } } = form;
  const run = useMutation({
    mutationFn: async (v: Values) => {
      const emi = await api<EmiResult>("/calculations/emi", { body: { principal: v.loan_amount, annual_rate: v.interest_rate, months: v.tenure_months } });
      const eligibility = await api<Eligibility>("/calculations/eligibility", { body: v });
      return { emi, eligibility };
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
  const result = run.data;
  const foirOk = result?.eligibility.foir !== undefined && result.eligibility.foir <= result.eligibility.foir_limit;
  const ltvOk = result?.eligibility.ltv !== undefined && result.eligibility.ltv <= result.eligibility.ltv_limit;
  return (
    <div>
      <PageHeader title="EMI and eligibility calculator" description="Indicative figures from the same formulas the underwriting engine uses. This is not a lending offer." />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,420px)_1fr]">
        <Card>
          <CardHeader title="Inputs" />
          <CardBody>
            <form className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1" onSubmit={handleSubmit((v) => run.mutate(v))} noValidate>
              <Field label="Product"><Select {...register("product")}><option value="HOME_LOAN">Home Loan</option><option value="LAP">Loan Against Property</option></Select></Field>
              <Field label="Evaluate under"><Select {...register("policy_key")}><option value="balanced">Balanced</option><option value="conservative">Conservative</option><option value="flexible">Flexible</option></Select></Field>
              <Field label="Employment type"><Select {...register("employment_type")}><option value="SALARIED">Salaried</option><option value="GOVT">Government employee</option><option value="SELF_EMPLOYED">Self employed</option></Select></Field>
              <Field label="Monthly net income (INR)" error={errors.monthly_income?.message}><Input type="number" {...register("monthly_income", { valueAsNumber: true })} /></Field>
              <Field label="Other monthly income (INR)" error={errors.other_income?.message}><Input type="number" {...register("other_income", { valueAsNumber: true })} /></Field>
              <Field label="Existing monthly EMIs (INR)" error={errors.existing_emi?.message}><Input type="number" {...register("existing_emi", { valueAsNumber: true })} /></Field>
              <Field label="Property value (INR)" error={errors.property_value?.message}><Input type="number" {...register("property_value", { valueAsNumber: true })} /></Field>
              <Field label="Loan amount (INR)" error={errors.loan_amount?.message}><Input type="number" {...register("loan_amount", { valueAsNumber: true })} /></Field>
              <Field label="Interest rate (% a year)" error={errors.interest_rate?.message}><Input type="number" step="0.05" {...register("interest_rate", { valueAsNumber: true })} /></Field>
              <Field label="Tenure (months)" error={errors.tenure_months?.message}><Input type="number" {...register("tenure_months", { valueAsNumber: true })} /></Field>
              <div className="sm:col-span-2 lg:col-span-1"><Button type="submit" className="w-full" loading={run.isPending}>Calculate</Button></div>
            </form>
          </CardBody>
        </Card>
        <div className="space-y-6">
          {!result && <Card><CardBody className="text-sm text-muted">Enter the details and calculate to see the EMI, FOIR, LTV and the indicative loan you may be eligible for.</CardBody></Card>}
          {result && (
            <>
              <Card>
                <CardHeader title="Repayment" description={result.emi.formula} />
                <CardBody className="grid gap-6 sm:grid-cols-3">
                  <Stat label="Monthly EMI" value={inr(result.emi.emi)} />
                  <Stat label="Total interest" value={inr(result.emi.total_interest, true)} />
                  <Stat label="Total payable" value={inr(result.emi.total_payable, true)} />
                </CardBody>
              </Card>
              <Card>
                <CardHeader title="Eligibility" description={`Under the ${result.eligibility.policy} policy`} />
                <CardBody className="space-y-5">
                  <div className="grid gap-6 sm:grid-cols-3">
                    <Stat label="Indicative eligible loan" value={inr(result.eligibility.indicative_eligible_loan, true)} hint="Lower of the FOIR and LTV limits" />
                    <Stat label="FOIR after this loan" value={pct(result.eligibility.foir)} tone={foirOk ? "ok" : "bad"} hint={`Limit ${pct(result.eligibility.foir_limit, 0)}`} />
                    <Stat label="LTV" value={pct(result.eligibility.ltv)} tone={ltvOk ? "ok" : "bad"} hint={`Limit ${pct(result.eligibility.ltv_limit, 0)}`} />
                  </div>
                  <KeyValue items={[
                    ["Eligible monthly income", inr(result.eligibility.eligible_income)],
                    ["Maximum affordable EMI", inr(result.eligibility.max_eligible_emi)],
                    ["Loan supported by FOIR", inr(result.eligibility.loan_by_foir)],
                    ["Loan supported by LTV", inr(result.eligibility.loan_by_ltv)],
                  ]} />
                  <div className="flex flex-wrap gap-2">
                    <Badge tone={foirOk ? "ok" : "bad"}>FOIR {foirOk ? "within" : "above"} limit</Badge>
                    <Badge tone={ltvOk ? "ok" : "bad"}>LTV {ltvOk ? "within" : "above"} limit</Badge>
                  </div>
                </CardBody>
              </Card>
              <Card>
                <CardHeader title="First 12 months" description="Interest and principal split of each instalment" />
                <CardBody>
                  <div className="h-64" role="img" aria-label="Principal and interest paid over the first twelve months">
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={result.emi.schedule_preview}>
                        <CartesianGrid stroke="#E2E4DC" vertical={false} />
                        <XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} />
                        <YAxis tickLine={false} axisLine={false} fontSize={12} tickFormatter={(v) => `${Math.round(v / 1000)}k`} width={44} />
                        <Tooltip formatter={(value: number) => inr(value)} labelFormatter={(m) => `Month ${m}`} />
                        <Area type="monotone" dataKey="principal" stackId="1" name="Principal" stroke="#244A36" fill="#244A36" fillOpacity={0.85} />
                        <Area type="monotone" dataKey="interest" stackId="1" name="Interest" stroke="#8FB39D" fill="#8FB39D" fillOpacity={0.8} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                </CardBody>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
