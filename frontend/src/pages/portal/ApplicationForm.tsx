import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useFieldArray, useForm, type FieldErrors } from "react-hook-form";
import { Link, useNavigate, useParams } from "react-router-dom";
import { z } from "zod";
import { PageHeader } from "@/components/Layout";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Spinner } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { useTitle } from "@/hooks/useTitle";
import { api, errorMessage } from "@/lib/api";
import type { Application } from "@/lib/types";
import { cn, inr, titleCase } from "@/lib/utils";

const number = (message: string) => z.number({ invalid_type_error: message, required_error: message });
const optionalNumber = z.number().nullable();

const applicantSchema = z.object({
  id: z.number().optional(),
  role: z.enum(["PRIMARY", "CO_APPLICANT"]),
  full_name: z.string().trim().min(2, "Enter the full name"),
  dob: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Enter the date of birth").refine((v) => (Date.now() - new Date(v).getTime()) / 31557600000 >= 18, "Applicants must be at least 18"),
  pan: z.string().trim().regex(/^[A-Za-z]{5}[0-9]{4}[A-Za-z]$/, "Enter a valid PAN, for example ABCDE1234F"),
  phone: z.string().regex(/^[6-9][0-9]{9}$/, "Enter a 10 digit mobile number"),
  email: z.string().email("Enter a valid email address"),
  address: z.string(),
  city: z.string(),
  employment_type: z.enum(["SALARIED", "GOVT", "SELF_EMPLOYED"]),
  employer: z.string(),
  years_in_job: number("Enter the years").min(0, "Cannot be negative"),
  monthly_income: number("Enter the monthly income").gt(0, "Income must be above zero"),
  other_income: number("Enter 0 if none").min(0, "Cannot be negative"),
  existing_emi: number("Enter 0 if none").min(0, "Cannot be negative"),
  business_type: z.string().nullable(),
  annual_turnover: optionalNumber,
  annual_itr_income: optionalNumber,
});

const schema = z.object({
  product: z.enum(["HOME_LOAN", "LAP"]),
  loan_amount: number("Enter the loan amount").gt(0, "Loan amount must be above zero"),
  interest_rate: number("Enter the rate").min(0, "Rate cannot be negative").max(40, "Rate cannot exceed 40%"),
  tenure_months: number("Enter the tenure").int("Whole months only").min(1, "At least 1 month").max(480, "At most 480 months"),
  purpose: z.string().trim().min(2, "Describe the purpose"),
  end_use: z.string().nullable(),
  property_type: z.enum(["APARTMENT", "INDEPENDENT_HOUSE", "PLOT", "COMMERCIAL", "AGRICULTURAL"]),
  property_subtype: z.enum(["RESIDENTIAL", "COMMERCIAL"]),
  property_city: z.string().trim().min(2, "Enter the city"),
  property_address: z.string(),
  property_pincode: z.string().regex(/^([0-9]{6})?$/, "Enter a 6 digit pincode"),
  property_area_sqft: number("Enter the area").min(0, "Cannot be negative"),
  survey_no: z.string(),
  declared_value: number("Enter the property value").gt(0, "Value must be above zero"),
  seller_name: z.string().nullable(),
  owner_name: z.string().nullable(),
  existing_mortgage_amount: number("Enter 0 if none").min(0, "Cannot be negative"),
  policy_key: z.enum(["balanced", "conservative", "flexible"]),
  applicants: z.array(applicantSchema).min(1).max(2),
  consents: z.record(z.boolean()),
});

type FormValues = z.infer<typeof schema>;

const consentText: Record<string, string> = {
  data_processing: "I agree to the processing of my application data for underwriting.",
  kyc: "I agree to KYC and identity verification, including authorised Aadhaar offline verification.",
  credit_bureau: "I agree to InnoNest retrieving my credit report from credit information companies.",
  bank_statement: "I agree to retrieval of my bank statements through an Account Aggregator.",
};

const emptyApplicant = (role: "PRIMARY" | "CO_APPLICANT") => ({
  role, full_name: "", dob: "", pan: "", phone: "", email: "", address: "", city: "", employment_type: "SALARIED" as const, employer: "", years_in_job: 0,
  monthly_income: undefined as unknown as number, other_income: 0, existing_emi: 0, business_type: null, annual_turnover: null, annual_itr_income: null,
});

const steps = [
  { title: "Loan", fields: ["product", "loan_amount", "interest_rate", "tenure_months", "purpose", "end_use"] },
  { title: "Property", fields: ["property_type", "property_subtype", "property_city", "property_address", "property_pincode", "property_area_sqft", "survey_no", "declared_value", "seller_name", "owner_name", "existing_mortgage_amount"] },
  { title: "Applicants", fields: ["applicants"] },
  { title: "Review", fields: ["consents"] },
] as const;

function toValues(application: Application): FormValues {
  return {
    product: application.product, loan_amount: application.loan_amount, interest_rate: application.interest_rate, tenure_months: application.tenure_months,
    purpose: application.purpose, end_use: application.end_use, property_type: application.property_type as FormValues["property_type"], property_subtype: "RESIDENTIAL",
    property_city: application.property_city, property_address: application.property_address, property_pincode: application.property_pincode,
    property_area_sqft: application.property_area_sqft, survey_no: application.survey_no, declared_value: application.declared_value, seller_name: application.seller_name,
    owner_name: application.owner_name, existing_mortgage_amount: application.existing_mortgage_amount, policy_key: application.policy_key as FormValues["policy_key"],
    applicants: application.applicants.map((a) => ({ ...a, role: a.role as "PRIMARY" | "CO_APPLICANT" } as FormValues["applicants"][number])), consents: application.consents,
  };
}

function ApplicantFields({ index, form, remove }: { index: number; form: ReturnType<typeof useForm<FormValues>>; remove?: () => void }) {
  const { register, watch, formState } = form;
  const errors = (formState.errors.applicants?.[index] ?? {}) as FieldErrors<FormValues["applicants"][number]>;
  const type = watch(`applicants.${index}.employment_type`);
  const self = type === "SELF_EMPLOYED";
  const path = (name: string) => `applicants.${index}.${name}` as `applicants.${number}.full_name`;
  return (
    <Card>
      <CardHeader
        title={index === 0 ? "Primary applicant" : "Co-applicant"}
        action={remove && <Button type="button" variant="ghost" size="sm" onClick={remove}><Trash2 className="h-4 w-4" /> Remove</Button>}
      />
      <CardBody className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name as on PAN" error={errors.full_name?.message}><Input {...register(path("full_name"))} /></Field>
        <Field label="Date of birth" error={errors.dob?.message}><Input type="date" {...register(path("dob"))} /></Field>
        <Field label="PAN" error={errors.pan?.message}><Input className="uppercase" maxLength={10} {...register(path("pan"))} /></Field>
        <Field label="Mobile number" error={errors.phone?.message}><Input inputMode="numeric" maxLength={10} {...register(path("phone"))} /></Field>
        <Field label="Email" error={errors.email?.message}><Input type="email" {...register(path("email"))} /></Field>
        <Field label="City" error={errors.city?.message}><Input {...register(path("city"))} /></Field>
        <Field label="Current address" className="sm:col-span-2" hint="If left blank we will ask for it after you submit."><Input {...register(path("address"))} /></Field>
        <Field label="Employment type" error={errors.employment_type?.message}>
          <Select {...register(path("employment_type"))}>
            <option value="SALARIED">Salaried</option>
            <option value="GOVT">Government employee</option>
            <option value="SELF_EMPLOYED">Self employed</option>
          </Select>
        </Field>
        {!self && <Field label="Employer" error={errors.employer?.message}><Input {...register(path("employer"))} /></Field>}
        {self && <Field label="Business type" error={errors.business_type?.message}><Input {...register(path("business_type"), { setValueAs: (v) => (v === "" ? null : v) })} /></Field>}
        <Field label={self ? "Years in business" : "Years in current job"} error={errors.years_in_job?.message}><Input type="number" step="0.5" {...register(path("years_in_job"), { valueAsNumber: true })} /></Field>
        <Field label="Monthly net income (INR)" error={errors.monthly_income?.message}><Input type="number" {...register(path("monthly_income"), { valueAsNumber: true })} /></Field>
        <Field label="Other monthly income (INR)" error={errors.other_income?.message}><Input type="number" {...register(path("other_income"), { valueAsNumber: true })} /></Field>
        <Field label="Existing monthly EMIs (INR)" error={errors.existing_emi?.message}><Input type="number" {...register(path("existing_emi"), { valueAsNumber: true })} /></Field>
        {self && (
          <>
            <Field label="Annual turnover (INR)" error={errors.annual_turnover?.message}><Input type="number" {...register(path("annual_turnover"), { setValueAs: (v) => (v === "" || v === null ? null : Number(v)) })} /></Field>
            <Field label="Annual income per latest ITR (INR)" error={errors.annual_itr_income?.message}><Input type="number" {...register(path("annual_itr_income"), { setValueAs: (v) => (v === "" || v === null ? null : Number(v)) })} /></Field>
          </>
        )}
      </CardBody>
    </Card>
  );
}

export default function ApplicationForm() {
  const { id } = useParams();
  const editing = Boolean(id);
  useTitle(editing ? "Update application" : "New application");
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);
  const existing = useQuery({ queryKey: ["application", id], queryFn: () => api<Application>(`/applications/${id}`), enabled: editing });
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      product: "HOME_LOAN", interest_rate: 8.5, tenure_months: 240, purpose: "", end_use: null, property_type: "APARTMENT", property_subtype: "RESIDENTIAL", property_city: "",
      property_address: "", property_pincode: "", property_area_sqft: 0, survey_no: "", declared_value: undefined as unknown as number, seller_name: null, owner_name: null,
      existing_mortgage_amount: 0, policy_key: "balanced", applicants: [emptyApplicant("PRIMARY")], consents: {},
    },
  });
  const { register, control, watch, formState, trigger, reset, handleSubmit, setValue } = form;
  const people = useFieldArray({ control, name: "applicants" });

  useEffect(() => {
    if (existing.data) reset(toValues(existing.data));
  }, [existing.data, reset]);

  const product = watch("product");
  const loan = watch("loan_amount");
  const rate = watch("interest_rate");
  const months = watch("tenure_months");
  const consents = watch("consents");
  const preview = useQuery({
    queryKey: ["emi", loan, rate, months],
    queryFn: () => api<{ emi: number; total_interest: number }>("/calculations/emi", { body: { principal: loan, annual_rate: rate, months } }),
    enabled: Number.isFinite(loan) && loan > 0 && Number.isFinite(rate) && rate >= 0 && rate <= 40 && Number.isFinite(months) && months >= 1 && months <= 480,
  });

  const save = useMutation({
    mutationFn: async (values: FormValues) => {
      const { consents: given, policy_key, product: productValue, property_subtype, ...rest } = values;
      const applicants = values.applicants.map((a) => ({ ...a, pan: a.pan.toUpperCase(), business_type: a.employment_type === "SELF_EMPLOYED" ? a.business_type : null }));
      if (editing) {
        const { purpose, end_use, ...tail } = rest;
        return api<Application>(`/applications/${id}`, { method: "PATCH", body: { ...tail, purpose, end_use: end_use || undefined, applicants } });
      }
      const created = await api<Application>("/applications", { body: { ...rest, product: productValue, policy_key, property_subtype, end_use: values.end_use || undefined, applicants } });
      const accepted = Object.fromEntries(Object.entries(given).filter(([, v]) => v));
      if (Object.keys(accepted).length) await api(`/applications/${created.id}/consents`, { body: { scopes: accepted } });
      return created;
    },
    onSuccess: (application) => {
      queryClient.invalidateQueries();
      toast.success(editing ? "Application updated" : "Application saved as a draft");
      navigate(`/portal/applications/${application.id}`);
    },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const next = async () => {
    const valid = await trigger(steps[step].fields as unknown as (keyof FormValues)[]);
    if (valid) setStep(step + 1);
    else toast.error("Please fix the highlighted fields");
  };

  const summary = useMemo(() => [["Product", titleCase(product)], ["Loan amount", inr(loan)], ["Rate and tenure", `${rate}% for ${months} months`], ["Estimated EMI", preview.data ? inr(preview.data.emi) : "-"]], [product, loan, rate, months, preview.data]);
  const errors = formState.errors;
  if (editing && existing.isLoading) return <Spinner />;

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title={editing ? "Update your application" : "Start an application"} description={editing ? "Add the missing details. We check them straight away." : "Four short steps. You can add documents after saving."}
        back={<Link to={editing ? `/portal/applications/${id}` : "/portal"} className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" /> Back</Link>} />
      <ol className="mb-6 grid grid-cols-4 gap-2" aria-label="Progress">
        {steps.map((s, index) => (
          <li key={s.title} className={cn("rounded-md border px-3 py-2 text-xs font-medium", index === step ? "border-brand bg-brand text-white" : index < step ? "border-brand/30 bg-brand-soft text-brand" : "border-line bg-white text-muted")}>
            {index + 1}. {s.title}
          </li>
        ))}
      </ol>
      <form onSubmit={handleSubmit((values) => save.mutate(values), () => toast.error("Please fix the highlighted fields"))} className="space-y-5" noValidate>
        {step === 0 && (
          <Card>
            <CardHeader title="Loan details" />
            <CardBody className="grid gap-4 sm:grid-cols-2">
              <Field label="Product">
                <Select disabled={editing} {...register("product")}>
                  <option value="HOME_LOAN">Home Loan</option>
                  <option value="LAP">Loan Against Property</option>
                </Select>
              </Field>
              <Field label="Loan amount (INR)" error={errors.loan_amount?.message}><Input type="number" {...register("loan_amount", { valueAsNumber: true })} /></Field>
              <Field label="Interest rate (% a year)" error={errors.interest_rate?.message}><Input type="number" step="0.05" {...register("interest_rate", { valueAsNumber: true })} /></Field>
              <Field label="Tenure (months)" error={errors.tenure_months?.message}><Input type="number" {...register("tenure_months", { valueAsNumber: true })} /></Field>
              <Field label="Purpose" error={errors.purpose?.message}><Input placeholder={product === "HOME_LOAN" ? "Purchase of residence" : "Business expansion"} {...register("purpose")} /></Field>
              {product === "LAP" && (
                <Field label="End use of funds" error={errors.end_use?.message}>
                  <Select {...register("end_use", { setValueAs: (v) => (v === "" ? null : v) })}>
                    <option value="">Select</option>
                    {["BUSINESS_EXPANSION", "WORKING_CAPITAL", "EDUCATION", "MEDICAL", "DEBT_CONSOLIDATION", "PERSONAL", "SPECULATIVE_INVESTMENT"].map((use) => <option key={use} value={use}>{titleCase(use)}</option>)}
                  </Select>
                </Field>
              )}
              {!editing && (
                <Field label="Evaluate under" hint="Lender policies are illustrative.">
                  <Select {...register("policy_key")}>
                    <option value="balanced">Balanced policy</option>
                    <option value="conservative">Conservative policy</option>
                    <option value="flexible">Flexible policy</option>
                  </Select>
                </Field>
              )}
              <div className="rounded-md bg-brand-tint p-3 text-sm sm:col-span-2">
                {preview.data ? <>Estimated EMI <strong>{inr(preview.data.emi)}</strong> a month, total interest {inr(preview.data.total_interest, true)}.</> : "Enter the amount, rate and tenure to see the EMI."}
              </div>
            </CardBody>
          </Card>
        )}
        {step === 1 && (
          <Card>
            <CardHeader title="Property" description="Details that are not known yet can be added later." />
            <CardBody className="grid gap-4 sm:grid-cols-2">
              <Field label="Property type" error={errors.property_type?.message}>
                <Select {...register("property_type")}>
                  {["APARTMENT", "INDEPENDENT_HOUSE", "PLOT", "COMMERCIAL", "AGRICULTURAL"].map((t) => <option key={t} value={t}>{titleCase(t)}</option>)}
                </Select>
              </Field>
              <Field label="Use"><Select {...register("property_subtype")}><option value="RESIDENTIAL">Residential</option><option value="COMMERCIAL">Commercial</option></Select></Field>
              <Field label="City" error={errors.property_city?.message}><Input {...register("property_city")} /></Field>
              <Field label="Pincode" error={errors.property_pincode?.message}><Input inputMode="numeric" maxLength={6} {...register("property_pincode")} /></Field>
              <Field label="Address" className="sm:col-span-2"><Input {...register("property_address")} /></Field>
              <Field label="Area (sq ft)" error={errors.property_area_sqft?.message}><Input type="number" {...register("property_area_sqft", { valueAsNumber: true })} /></Field>
              <Field label="Survey or plot number"><Input {...register("survey_no")} /></Field>
              <Field label="Declared property value (INR)" error={errors.declared_value?.message}><Input type="number" {...register("declared_value", { valueAsNumber: true })} /></Field>
              <Field label="Existing mortgage on the property (INR)" error={errors.existing_mortgage_amount?.message}><Input type="number" {...register("existing_mortgage_amount", { valueAsNumber: true })} /></Field>
              {product === "HOME_LOAN" && <Field label="Seller name"><Input {...register("seller_name", { setValueAs: (v) => (v === "" ? null : v) })} /></Field>}
              <Field label="Current owner name"><Input {...register("owner_name", { setValueAs: (v) => (v === "" ? null : v) })} /></Field>
            </CardBody>
          </Card>
        )}
        {step === 2 && (
          <>
            {people.fields.map((field, index) => <ApplicantFields key={field.id} index={index} form={form} remove={index > 0 && !editing ? () => people.remove(index) : undefined} />)}
            {people.fields.length < 2 && !editing && (
              <Button type="button" variant="outline" onClick={() => people.append(emptyApplicant("CO_APPLICANT"))}><Plus className="h-4 w-4" /> Add a co-applicant</Button>
            )}
          </>
        )}
        {step === 3 && (
          <Card>
            <CardHeader title={editing ? "Review your changes" : "Review and consent"} />
            <CardBody className="space-y-5">
              <dl className="grid gap-3 sm:grid-cols-2">
                {summary.map(([k, v]) => <div key={k}><dt className="label-sm">{k}</dt><dd className="text-sm font-medium">{v}</dd></div>)}
              </dl>
              {!editing && (
                <div className="space-y-3">
                  <p className="text-sm text-muted">We only use these permissions to underwrite this application. You can still save without them, but we cannot process the application until all four are given.</p>
                  {Object.entries(consentText).map(([key, text]) => (
                    <label key={key} className="flex items-start gap-3 text-sm">
                      <input type="checkbox" className="mt-1 h-4 w-4 accent-[#244A36]" checked={Boolean(consents[key])} onChange={(event) => setValue(`consents.${key}`, event.target.checked)} />
                      {text}
                    </label>
                  ))}
                </div>
              )}
            </CardBody>
          </Card>
        )}
        <div className="flex items-center justify-between">
          <Button type="button" variant="outline" disabled={step === 0} onClick={() => setStep(step - 1)}><ArrowLeft className="h-4 w-4" /> Previous</Button>
          {step < steps.length - 1 ? (
            <Button type="button" onClick={next}>Continue <ArrowRight className="h-4 w-4" /></Button>
          ) : (
            <Button type="submit" loading={save.isPending}>{editing ? "Save changes" : "Save draft"}</Button>
          )}
        </div>
      </form>
    </div>
  );
}
