import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, RefreshCw, RotateCw } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Checklist } from "@/components/Checklist";
import { DocumentViewer } from "@/components/DocumentViewer";
import { PageHeader } from "@/components/Layout";
import { StatusStepper } from "@/components/StatusStepper";
import { Timeline } from "@/components/Timeline";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/dialog";
import { EmptyState, ErrorNotice, KeyValue, Spinner } from "@/components/ui/feedback";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { useTitle } from "@/hooks/useTitle";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Application, AuditEvent, Checklist as ChecklistData, DocRequest, DocumentRecord, Page } from "@/lib/types";
import { dateOnly, dateTime, docLabel, inr, titleCase } from "@/lib/utils";
import { DecisionTab } from "./detail/DecisionTab";
import { EvidenceTab } from "./detail/EvidenceTab";
import { FinancialTab } from "./detail/FinancialTab";
import { PropertyTab } from "./detail/PropertyTab";
import { RiskTab } from "./detail/RiskTab";
import { VerificationTab } from "./detail/VerificationTab";

function AuditTab({ applicationId }: { applicationId: number }) {
  const events = useQuery({ queryKey: ["audit", "application", applicationId], queryFn: () => api<Page<AuditEvent>>("/audit", { params: { application_id: applicationId, page_size: 100 } }) });
  if (events.isLoading) return <Spinner />;
  const rows = events.data?.items ?? [];
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
      <Card>
        <CardHeader title="Audit records" description="Every action on this application, newest first." />
        {rows.length === 0 ? <EmptyState title="No records" /> : (
          <Table>
            <thead><tr><Th>#</Th><Th>When</Th><Th>Actor</Th><Th>Action</Th><Th>Hash</Th></tr></thead>
            <tbody>
              {rows.map((e) => (
                <Tr key={e.id}><Td>{e.id}</Td><Td className="whitespace-nowrap">{dateTime(e.created_at)}</Td><Td>{e.actor}<div className="text-xs text-muted">{e.actor_role}</div></Td><Td><Badge>{e.action}</Badge></Td><Td className="font-mono text-xs text-muted">{e.hash.slice(0, 10)}</Td></Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      <Card className="self-start"><CardHeader title="Timeline" /><CardBody><Timeline applicationId={applicationId} /></CardBody></Card>
    </div>
  );
}

export default function WorkspaceApplicationDetail() {
  const { id } = useParams();
  const applicationId = Number(id);
  const { user } = useAuth();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [viewing, setViewing] = useState<number | null>(null);
  const [confirm, setConfirm] = useState<"reevaluate" | "retry" | null>(null);
  const isUnderwriter = user?.role === "underwriter";
  const canOperate = isUnderwriter || user?.role === "policy_admin";
  const application = useQuery({ queryKey: ["application", id], queryFn: () => api<Application>(`/applications/${applicationId}`) });
  const checklist = useQuery({ queryKey: ["checklist", id], queryFn: () => api<ChecklistData>(`/applications/${applicationId}/checklist`), enabled: application.isSuccess });
  const requests = useQuery({ queryKey: ["requests", id], queryFn: () => api<DocRequest[]>(`/applications/${applicationId}/requests`), enabled: application.isSuccess });
  const documents = useQuery({ queryKey: ["documents", id], queryFn: () => api<DocumentRecord[]>(`/applications/${applicationId}/documents`), enabled: application.isSuccess });
  useTitle(application.data?.reference ?? "Application");

  const action = useMutation({
    mutationFn: (kind: "reevaluate" | "retry") => api<{ status: string }>(`/applications/${applicationId}/${kind === "retry" ? "retry-verification" : "reevaluate"}`, { method: "POST" }),
    onSuccess: (result) => { toast.success(`Application is now ${titleCase(result.status).toLowerCase()}`); setConfirm(null); queryClient.invalidateQueries(); },
    onError: (e) => { toast.error(errorMessage(e)); setConfirm(null); },
  });

  if (application.isLoading) return <Spinner />;
  if (application.isError || !application.data) return <ErrorNotice message={errorMessage(application.error)} onRetry={() => application.refetch()} />;
  const app = application.data;
  const open = (requests.data ?? []).filter((r) => r.status === "OPEN");

  return (
    <div className="space-y-6">
      <PageHeader
        back={<Link to="/workspace/applications" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" /> Application register</Link>}
        title={app.reference}
        description={<span className="flex flex-wrap items-center gap-2"><StatusBadge status={app.status} /> {titleCase(app.product)} · {inr(app.loan_amount)} · {app.applicants[0]?.full_name} · {titleCase(app.policy_key)} policy</span>}
        actions={
          <>
            {isUnderwriter && app.status === "REFERRED" && <Button variant="outline" onClick={() => setConfirm("reevaluate")}><RefreshCw className="h-4 w-4" /> Re-evaluate</Button>}
            {canOperate && app.status === "VERIFICATION_PENDING" && <Button variant="outline" onClick={() => setConfirm("retry")}><RotateCw className="h-4 w-4" /> Retry verification</Button>}
          </>
        }
      />
      <Card><CardBody><StatusStepper status={app.status} /></CardBody></Card>
      <Tabs defaultValue="summary">
        <TabsList className="flex-wrap">
          <TabsTrigger value="summary">Summary</TabsTrigger>
          <TabsTrigger value="verification">Verification</TabsTrigger>
          <TabsTrigger value="financial">Financial</TabsTrigger>
          <TabsTrigger value="risk">Risk</TabsTrigger>
          <TabsTrigger value="property">Property</TabsTrigger>
          <TabsTrigger value="decision">Decision</TabsTrigger>
          <TabsTrigger value="evidence">Evidence graph</TabsTrigger>
          <TabsTrigger value="audit">Audit</TabsTrigger>
        </TabsList>
        <TabsContent value="summary" className="space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader title="Loan and property" />
              <CardBody>
                <KeyValue items={[
                  ["Purpose", app.purpose], ["End use", titleCase(app.end_use)], ["Interest rate", `${app.interest_rate}% a year`], ["Tenure", `${app.tenure_months} months`],
                  ["Property", `${titleCase(app.property_type)}, ${app.property_city}`], ["Survey number", app.survey_no || "-"], ["Declared value", inr(app.declared_value)], ["Existing mortgage", inr(app.existing_mortgage_amount)],
                  ["Seller", app.seller_name ?? "-"], ["Owner", app.owner_name ?? "-"], ["Submitted", dateTime(app.submitted_at)], ["Decided", dateTime(app.decided_at)],
                ]} />
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Applicants" />
              <CardBody className="space-y-3">
                {app.applicants.map((a) => (
                  <div key={a.id} className="rounded-md border border-line p-3">
                    <p className="text-sm font-medium">{a.full_name} <span className="font-normal text-muted">· {titleCase(a.role)}</span></p>
                    <p className="mt-1 text-xs text-muted">{titleCase(a.employment_type)} · {a.employer || a.business_type || "-"} · {a.years_in_job} years</p>
                    <p className="text-xs text-muted">Declared income {inr(a.monthly_income)} · Existing EMIs {inr(a.existing_emi)} · PAN {a.pan}</p>
                    <p className="text-xs text-muted">Born {dateOnly(a.dob)} · {a.phone} · {a.email}</p>
                  </div>
                ))}
              </CardBody>
            </Card>
          </div>
          {open.length > 0 && (
            <Card>
              <CardHeader title="Waiting on the applicant" description={`${open.length} open request${open.length === 1 ? "" : "s"}`} />
              <Table>
                <thead><tr><Th>Request</Th><Th>Status</Th><Th>Reminders</Th><Th>Due</Th></tr></thead>
                <tbody>{open.map((r) => <Tr key={r.id}><Td>{r.title}<div className="text-xs text-muted">{r.message}</div></Td><Td><StatusBadge status={r.status} /></Td><Td>{r.reminders_sent}</Td><Td>{dateOnly(r.due_at)}</Td></Tr>)}</tbody>
              </Table>
            </Card>
          )}
          <Card>
            <CardHeader title="Evidence checklist" description={checklist.data ? (checklist.data.complete ? "Everything required has been received." : `${checklist.data.open_count} of ${checklist.data.total} items open`) : undefined} />
            <CardBody>
              {checklist.data && <Checklist application={app} checklist={checklist.data} requests={requests.data ?? []} editable={false} onViewDocument={setViewing} />}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Documents" description="Reading confidence and integrity indicators describe the file. They do not prove it is authentic." />
            {(documents.data ?? []).length === 0 ? <EmptyState title="No documents" /> : (
              <Table>
                <thead><tr><Th>Document</Th><Th>File</Th><Th>Reading</Th><Th>Confidence</Th><Th>Indicators</Th><Th /></tr></thead>
                <tbody>
                  {documents.data!.map((d) => (
                    <Tr key={d.id}>
                      <Td className="font-medium">{docLabel(d.doc_type)}</Td>
                      <Td className="max-w-[180px] truncate" title={d.original_name}>{d.original_name}</Td>
                      <Td><StatusBadge status={d.extraction_status} />{d.ocr_used && <Badge className="ml-1">OCR</Badge>}</Td>
                      <Td>{d.confidence === null ? "-" : `${Math.round(d.confidence * 100)}%`}</Td>
                      <Td>{d.findings.length === 0 ? <span className="text-muted">None</span> : <Badge tone="warn">{d.findings.length} to review</Badge>}</Td>
                      <Td><Button variant="ghost" size="sm" onClick={() => setViewing(d.id)}>Open</Button></Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>
        </TabsContent>
        <TabsContent value="verification"><VerificationTab application={app} canReview={isUnderwriter} /></TabsContent>
        <TabsContent value="financial"><FinancialTab applicationId={app.id} /></TabsContent>
        <TabsContent value="risk"><RiskTab applicationId={app.id} /></TabsContent>
        <TabsContent value="property"><PropertyTab applicationId={app.id} /></TabsContent>
        <TabsContent value="decision"><DecisionTab application={app} canReview={isUnderwriter} /></TabsContent>
        <TabsContent value="evidence"><EvidenceTab applicationId={app.id} /></TabsContent>
        <TabsContent value="audit"><AuditTab applicationId={app.id} /></TabsContent>
      </Tabs>
      <DocumentViewer documentId={viewing} canEdit={isUnderwriter} onClose={() => setViewing(null)} />
      <ConfirmDialog
        open={confirm === "reevaluate"} onOpenChange={(o) => !o && setConfirm(null)} title="Re-evaluate this application?"
        description="The engine runs again on the current documents and the active policy. A new decision is recorded." confirmLabel="Re-evaluate" loading={action.isPending} onConfirm={() => action.mutate("reevaluate")}
      />
      <ConfirmDialog
        open={confirm === "retry"} onOpenChange={(o) => !o && setConfirm(null)} title="Retry verification?"
        description="The held verification sources are called again. If they respond, underwriting resumes." confirmLabel="Retry" loading={action.isPending} onConfirm={() => action.mutate("retry")}
      />
    </div>
  );
}
