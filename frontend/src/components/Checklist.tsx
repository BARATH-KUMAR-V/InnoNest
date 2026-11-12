import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, FileUp, MessageSquareText, PencilLine } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import type { Application, Checklist as ChecklistData, ChecklistItem, DocRequest } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  application: Application;
  checklist: ChecklistData;
  requests: DocRequest[];
  editable: boolean;
  onViewDocument: (id: number) => void;
}

function UploadButton({ item, application, label }: { item: ChecklistItem; application: Application; label: string }) {
  const input = useRef<HTMLInputElement>(null);
  const queryClient = useQueryClient();
  const toast = useToast();
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.set("doc_type", item.doc_type as string);
      if (item.applicant_id) form.set("applicant_id", String(item.applicant_id));
      form.set("file", file);
      return api(`/applications/${application.id}/documents`, { form });
    },
    onSuccess: () => {
      toast.success("Document received and checked");
      queryClient.invalidateQueries();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
  return (
    <>
      <input
        ref={input}
        type="file"
        accept=".pdf,.png,.jpg,.jpeg"
        className="sr-only"
        aria-label={`${label} ${item.title}`}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) upload.mutate(file);
          event.target.value = "";
        }}
      />
      <Button size="sm" variant={item.status === "OPEN" ? "primary" : "outline"} loading={upload.isPending} onClick={() => input.current?.click()}>
        <FileUp className="h-3.5 w-3.5" />
        {label}
      </Button>
    </>
  );
}

type ClarifyTarget = DocRequest & { application_id: number };

function ClarifyDialog({ request, onClose }: { request: ClarifyTarget | null; onClose: () => void }) {
  const [text, setText] = useState("");
  const queryClient = useQueryClient();
  const toast = useToast();
  const send = useMutation({
    mutationFn: () => api(`/applications/${request!.application_id}/clarifications`, { body: { request_id: request!.id, response: text } }),
    onSuccess: () => {
      toast.success("Your explanation was sent");
      setText("");
      onClose();
      queryClient.invalidateQueries();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
  return (
    <Dialog open={request !== null} onOpenChange={(open) => !open && onClose()} title="Explain the difference" description={request?.message}>
      <Textarea value={text} onChange={(event) => setText(event.target.value)} placeholder="For example: my name on the PAN card was recorded after marriage." />
      <div className="mt-4 flex justify-end gap-2">
        <Button variant="outline" onClick={onClose}>Cancel</Button>
        <Button disabled={text.trim().length < 5} loading={send.isPending} onClick={() => send.mutate()}>Send explanation</Button>
      </div>
    </Dialog>
  );
}

export function Checklist({ application, checklist, requests, editable, onViewDocument }: Props) {
  const [clarifying, setClarifying] = useState<ClarifyTarget | null>(null);
  const queryClient = useQueryClient();
  const toast = useToast();
  const consent = useMutation({
    mutationFn: (key: string) => api(`/applications/${application.id}/consents`, { body: { scopes: { [key]: true } } }),
    onSuccess: () => {
      toast.success("Consent recorded");
      queryClient.invalidateQueries();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
  const requestFor = (item: ChecklistItem) => requests.find((r) => r.item_key === item.key && r.status === "OPEN");
  const sorted = [...checklist.items].sort((a, b) => Number(a.status !== "OPEN") - Number(b.status !== "OPEN"));
  const groups = { OPEN: sorted.filter((i) => i.status === "OPEN"), EXPLAINED: sorted.filter((i) => i.status === "EXPLAINED"), SATISFIED: sorted.filter((i) => i.status === "SATISFIED") };

  const renderAction = (item: ChecklistItem) => {
    if (!editable) return null;
    if (item.kind === "MISSING_DOCUMENT" || item.kind === "UNREADABLE_DOCUMENT" || item.kind === "WRONG_DOCUMENT") return <UploadButton item={item} application={application} label={item.kind === "MISSING_DOCUMENT" ? "Upload" : "Upload again"} />;
    if (item.kind === "DOCUMENT") return <UploadButton item={item} application={application} label="Replace" />;
    if (item.kind === "MISSING_FIELD")
      return (
        <Button asChild size="sm" variant="outline">
          <Link to={`/portal/applications/${application.id}/edit`}><PencilLine className="h-3.5 w-3.5" /> Update details</Link>
        </Button>
      );
    if (item.kind === "CONSENT") {
      const key = item.key.replace("consent:", "");
      return <Button size="sm" loading={consent.isPending} onClick={() => consent.mutate(key)}>I agree</Button>;
    }
    if (item.kind === "CONFLICT") {
      const request = requestFor(item);
      return (
        <div className="flex gap-2">
          <Button asChild size="sm" variant="outline"><Link to={`/portal/applications/${application.id}/edit`}><PencilLine className="h-3.5 w-3.5" /> Correct</Link></Button>
          {request && <Button size="sm" variant="outline" onClick={() => setClarifying({ ...request, application_id: application.id })}><MessageSquareText className="h-3.5 w-3.5" /> Explain</Button>}
        </div>
      );
    }
    return null;
  };

  const row = (item: ChecklistItem) => (
    <li key={item.key} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
      <div className="flex min-w-0 items-start gap-3">
        {item.status === "SATISFIED" ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" /> : <AlertCircle className={cn("mt-0.5 h-4 w-4 shrink-0", item.status === "OPEN" ? "text-warn" : "text-info")} />}
        <div className="min-w-0">
          <p className="text-sm font-medium">
            {item.title}
            {item.applicant_name && <span className="font-normal text-muted"> · {item.applicant_name}</span>}
          </p>
          <p className={cn("text-sm", item.status === "OPEN" ? "text-ink" : "text-muted")}>{item.message}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        {item.status === "SATISFIED" && item.document_id && <Button size="sm" variant="ghost" onClick={() => onViewDocument(item.document_id as number)}>View</Button>}
        {item.status === "EXPLAINED" && <Badge tone="info">Awaiting review</Badge>}
        {item.status === "OPEN" && <StatusBadge status={item.kind === "MISSING_DOCUMENT" ? "OPEN" : item.kind} className="hidden sm:inline-flex" />}
        {renderAction(item)}
      </div>
    </li>
  );

  return (
    <>
      {groups.OPEN.length > 0 && <ul className="divide-y divide-line">{groups.OPEN.map(row)}</ul>}
      {groups.EXPLAINED.length > 0 && <ul className="divide-y divide-line border-t border-line">{groups.EXPLAINED.map(row)}</ul>}
      {groups.SATISFIED.length > 0 && (
        <>
          <p className="label-sm border-t border-line bg-brand-tint px-5 py-2">Received</p>
          <ul className="divide-y divide-line">{groups.SATISFIED.map(row)}</ul>
        </>
      )}
      <ClarifyDialog request={clarifying} onClose={() => setClarifying(null)} />
    </>
  );
}
