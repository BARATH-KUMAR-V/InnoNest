import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, Clock, FileText, Pencil, Send, Undo2 } from "lucide-react";
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
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { useTitle } from "@/hooks/useTitle";
import { api, errorMessage } from "@/lib/api";
import type { Application, Checklist as ChecklistData, Decision, DocRequest, DocumentRecord } from "@/lib/types";
import { dateOnly, dateTime, docLabel, inr, titleCase } from "@/lib/utils";

const closedMessage: Record<string, string> = {
  APPROVED: "Your application was approved under the lender's policy.",
  REJECTED: "Your application was not approved under the lender's policy.",
  REFERRED: "Your application has been referred to an underwriter for a manual review.",
  EXPIRED: "This application expired because the requested information did not arrive in time. You can start a new application.",
  WITHDRAWN: "You withdrew this application.",
  VERIFICATION_PENDING: "We are waiting for a verification source to respond. We will resume as soon as it does and you need not do anything.",
  PROCESSING: "We are checking your application now.",
  SUBMITTED: "Your application has been received.",
  DOCUMENTS_RECEIVED: "We have received your documents and are checking them.",
};

export default function PortalApplicationDetail() {
  const { id } = useParams();
  const applicationId = Number(id);
  const toast = useToast();
  const queryClient = useQueryClient();
  const [viewing, setViewing] = useState<number | null>(null);
  const [confirm, setConfirm] = useState<"submit" | "withdraw" | null>(null);
  const application = useQuery({ queryKey: ["application", id], queryFn: () => api<Application>(`/applications/${applicationId}`), refetchInterval: (query) => (["PROCESSING", "SUBMITTED"].includes(query.state.data?.status ?? "") ? 3000 : false) });
  const checklist = useQuery({ queryKey: ["checklist", id], queryFn: () => api<ChecklistData>(`/applications/${applicationId}/checklist`), enabled: application.isSuccess });
  const requests = useQuery({ queryKey: ["requests", id], queryFn: () => api<DocRequest[]>(`/applications/${applicationId}/requests`), enabled: application.isSuccess });
  const documents = useQuery({ queryKey: ["documents", id], queryFn: () => api<DocumentRecord[]>(`/applications/${applicationId}/documents`), enabled: application.isSuccess });
  const decisions = useQuery({ queryKey: ["decisions", id], queryFn: () => api<Decision[]>(`/applications/${applicationId}/decisions`), enabled: application.isSuccess });
  useTitle(application.data ? application.data.reference : "Application");

  const refresh = () => queryClient.invalidateQueries();
  const submit = useMutation({
    mutationFn: () => api<Application>(`/applications/${applicationId}/submit`, { method: "POST" }),
    onSuccess: (result) => { toast.success(result.status === "ACTION_REQUIRED" ? "Submitted. We need a few more things from you" : "Application submitted"); setConfirm(null); refresh(); },
    onError: (error) => { toast.error(errorMessage(error)); setConfirm(null); },
  });
  const withdraw = useMutation({
    mutationFn: () => api<Application>(`/applications/${applicationId}/withdraw`, { method: "POST" }),
    onSuccess: () => { toast.success("Application withdrawn"); setConfirm(null); refresh(); },
    onError: (error) => { toast.error(errorMessage(error)); setConfirm(null); },
  });

  if (application.isLoading) return <Spinner />;
  if (application.isError || !application.data) return <ErrorNotice message={errorMessage(application.error)} onRetry={() => application.refetch()} />;
  const app = application.data;
  const editable = ["DRAFT", "ACTION_REQUIRED"].includes(app.status);
  const closed = ["APPROVED", "REJECTED", "EXPIRED", "WITHDRAWN"].includes(app.status);
  const canWithdraw = !["WITHDRAWN", "EXPIRED", "APPROVED", "REJECTED"].includes(app.status);
  const open = (requests.data ?? []).filter((r) => r.status === "OPEN");
  const nextDue = open.map((r) => r.due_at).filter(Boolean).sort()[0] ?? app.expires_at;
  const decision = decisions.data?.[0];

  return (
    <div className="space-y-6">
      <PageHeader
        back={<Link to="/portal" className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-ink"><ArrowLeft className="h-4 w-4" /> My applications</Link>}
        title={app.reference}
        description={<span className="flex flex-wrap items-center gap-2"><StatusBadge status={app.status} /> {titleCase(app.product)} · {inr(app.loan_amount)} · {app.tenure_months} months</span>}
        actions={
          <>
            {editable && <Button variant="outline" asChild><Link to={`/portal/applications/${app.id}/edit`}><Pencil className="h-4 w-4" /> Edit details</Link></Button>}
            {app.status === "DRAFT" && <Button onClick={() => setConfirm("submit")}><Send className="h-4 w-4" /> Submit application</Button>}
            {canWithdraw && <Button variant="outline" onClick={() => setConfirm("withdraw")}><Undo2 className="h-4 w-4" /> Withdraw</Button>}
          </>
        }
      />
      <Card><CardBody><StatusStepper status={app.status} /></CardBody></Card>

      {app.status === "ACTION_REQUIRED" && (
        <div className="flex gap-3 rounded-lg border border-warn/30 bg-warn-soft p-4" role="status">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-warn" />
          <div className="text-sm">
            <p className="font-semibold text-warn">We need {open.length || "a few"} more {open.length === 1 ? "thing" : "things"} from you</p>
            <p className="mt-1">Complete the items below and we will carry on automatically. You do not need to resubmit.</p>
            {nextDue && <p className="mt-1 flex items-center gap-1 text-xs"><Clock className="h-3.5 w-3.5" /> Please respond by {dateOnly(nextDue)}. After that the application expires.</p>}
          </div>
        </div>
      )}
      {app.status !== "ACTION_REQUIRED" && app.status !== "DRAFT" && closedMessage[app.status] && (
        <div className="rounded-lg border border-line bg-white p-4 text-sm" role="status">{closedMessage[app.status]}</div>
      )}
      {app.status === "DRAFT" && <div className="rounded-lg border border-line bg-white p-4 text-sm">This application is a draft. Add your documents below, then submit it. Items we cannot yet see are listed as missing and nothing is rejected for that.</div>}

      {decision && closed && (
        <Card>
          <CardHeader title="Decision" description={`${decision.policy_name} policy, version ${decision.policy_version}`} action={<StatusBadge status={decision.outcome} />} />
          <CardBody className="space-y-3">
            <p className="text-sm">{decision.explanation}</p>
            {decision.reason_codes.length > 0 && (
              <ul className="space-y-1 text-sm text-muted">
                {decision.reason_codes.map((r) => <li key={r.code}>{r.message}</li>)}
              </ul>
            )}
            <p className="text-xs text-muted">Decided on {dateTime(decision.created_at)}. Decisions follow written lender rules and are made by the underwriting engine or a human underwriter.</p>
          </CardBody>
        </Card>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <Card>
            <CardHeader
              title="What we need from you"
              description={checklist.data ? (checklist.data.complete ? "Everything required has been received." : `${checklist.data.open_count} of ${checklist.data.total} items still open`) : undefined}
            />
            <CardBody>
              {checklist.isLoading && <Spinner />}
              {checklist.data && <Checklist application={app} checklist={checklist.data} requests={requests.data ?? []} editable={editable || ["VERIFICATION_PENDING", "REFERRED"].includes(app.status)} onViewDocument={setViewing} />}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Documents" description="Files you have uploaded. Each upload is read automatically." />
            {documents.isLoading && <Spinner />}
            {documents.data && documents.data.length === 0 && <EmptyState title="No documents yet" description="Upload the documents listed above." icon={<FileText className="h-6 w-6" />} />}
            {documents.data && documents.data.length > 0 && (
              <Table>
                <thead><tr><Th>Document</Th><Th>File</Th><Th>Reading</Th><Th>Uploaded</Th><Th /></tr></thead>
                <tbody>
                  {documents.data.map((d) => (
                    <Tr key={d.id}>
                      <Td className="font-medium">{docLabel(d.doc_type)}</Td>
                      <Td className="max-w-[200px] truncate" title={d.original_name}>{d.original_name}</Td>
                      <Td><StatusBadge status={d.extraction_status} />{d.ocr_used && <Badge className="ml-1">OCR</Badge>}</Td>
                      <Td>{dateTime(d.uploaded_at)}</Td>
                      <Td><Button variant="ghost" size="sm" onClick={() => setViewing(d.id)}>View</Button></Td>
                    </Tr>
                  ))}
                </tbody>
              </Table>
            )}
          </Card>
          <Card>
            <CardHeader title="Application details" />
            <CardBody className="space-y-5">
              <KeyValue items={[
                ["Purpose", app.purpose], ["Interest rate", `${app.interest_rate}% a year`],
                ["Property", `${titleCase(app.property_type)}, ${app.property_city}`], ["Declared property value", inr(app.declared_value)],
                ["Evaluation policy", titleCase(app.policy_key)], ["Submitted", dateTime(app.submitted_at)],
              ]} />
              {app.applicants.map((a) => (
                <div key={a.id} className="rounded-md border border-line p-3">
                  <p className="text-sm font-medium">{a.full_name} <span className="font-normal text-muted">· {titleCase(a.role)}</span></p>
                  <p className="mt-1 text-xs text-muted">{titleCase(a.employment_type)} · Monthly income {inr(a.monthly_income)} · PAN {a.pan.slice(0, 2)}XXXXX{a.pan.slice(-2)}</p>
                </div>
              ))}
            </CardBody>
          </Card>
        </div>
        <Card className="self-start">
          <CardHeader title="History" />
          <CardBody><Timeline applicationId={app.id} /></CardBody>
        </Card>
      </div>

      <DocumentViewer documentId={viewing} canEdit={false} onClose={() => setViewing(null)} />
      <ConfirmDialog
        open={confirm === "submit"} onOpenChange={(o) => !o && setConfirm(null)} title="Submit this application?"
        description="We will start checking it straight away. If something is missing we will tell you what is needed. You can still add documents afterwards." confirmLabel="Submit" loading={submit.isPending} onConfirm={() => submit.mutate()}
      />
      <ConfirmDialog
        open={confirm === "withdraw"} onOpenChange={(o) => !o && setConfirm(null)} title="Withdraw this application?"
        description="Underwriting stops and this cannot be undone. You can start a new application at any time." confirmLabel="Withdraw" danger loading={withdraw.isPending} onConfirm={() => withdraw.mutate()}
      />
    </div>
  );
}
