import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, Pencil, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/form";
import { Spinner } from "@/components/ui/feedback";
import { useToast } from "@/components/ui/toast";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { api, errorMessage, openFile } from "@/lib/api";
import type { DocumentRecord, FieldRecord } from "@/lib/types";
import { titleCase } from "@/lib/utils";

interface Detail {
  document: DocumentRecord;
  fields: FieldRecord[];
  text_excerpt: string | null;
  notice: string;
}

function FieldRow({ field, canEdit, onSaved }: { field: FieldRecord; canEdit: boolean; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(field.effective_value);
  const toast = useToast();
  const save = useMutation({
    mutationFn: () => api(`/document-fields/${field.id}`, { method: "PATCH", body: { value } }),
    onSuccess: () => {
      toast.success("Value updated and the application re-checked");
      setEditing(false);
      onSaved();
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
  return (
    <Tr>
      <Td className="font-medium">{titleCase(field.name)}</Td>
      <Td>
        {editing ? (
          <div className="flex gap-2">
            <Input value={value} onChange={(event) => setValue(event.target.value)} className="h-8" />
            <Button size="sm" loading={save.isPending} onClick={() => save.mutate()}>Save</Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
          </div>
        ) : (
          <span>
            {field.effective_value}
            {field.corrected_value !== null && <span className="ml-2 text-xs text-muted">(read as {field.value})</span>}
          </span>
        )}
      </Td>
      <Td className={field.confidence < 0.8 ? "text-warn" : "text-muted"}>{Math.round(field.confidence * 100)}%</Td>
      <Td className="text-right">
        {canEdit && !editing && (
          <Button size="icon" variant="ghost" aria-label={`Correct ${field.name}`} onClick={() => setEditing(true)}>
            <Pencil className="h-4 w-4" />
          </Button>
        )}
      </Td>
    </Tr>
  );
}

export function DocumentViewer({ documentId, canEdit, onClose, onChanged }: { documentId: number | null; canEdit: boolean; onClose: () => void; onChanged?: () => void }) {
  const queryClient = useQueryClient();
  const detail = useQuery({ queryKey: ["document", documentId], queryFn: () => api<Detail>(`/documents/${documentId}`), enabled: documentId !== null });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["document", documentId] });
    onChanged?.();
  };
  const doc = detail.data?.document;
  return (
    <Dialog open={documentId !== null} onOpenChange={(open) => !open && onClose()} title={doc ? doc.original_name : "Document"} description="Values read from the file. Check them and correct anything that is wrong." wide>
      {detail.isLoading || !detail.data || !doc ? (
        <Spinner />
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <StatusBadge status={doc.extraction_status} />
            {doc.ocr_used && <Badge tone="info">Read with OCR</Badge>}
            <span className="text-muted">Confidence {doc.confidence !== null ? Math.round(doc.confidence * 100) : "-"}%</span>
            <span className="text-muted">·</span>
            <span className="font-mono text-xs text-muted" title={doc.sha256}>SHA-256 {doc.sha256.slice(0, 16)}…</span>
            <Button size="sm" variant="outline" className="ml-auto" onClick={() => openFile(`/documents/${doc.id}/file`)}>
              <ExternalLink className="h-3.5 w-3.5" /> Open file
            </Button>
          </div>
          {doc.findings.length > 0 && (
            <div className="rounded-md border border-warn/30 bg-warn-soft p-3 text-sm">
              <p className="mb-1 flex items-center gap-1.5 font-medium text-warn"><ShieldAlert className="h-4 w-4" /> Points noted on this file</p>
              <ul className="list-disc space-y-1 pl-5">
                {doc.findings.map((finding) => (
                  <li key={finding.id}>
                    {finding.text} <span className="text-xs text-muted">({finding.id})</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {detail.data.fields.length === 0 ? (
            <p className="text-sm text-muted">No structured values were read from this file.</p>
          ) : (
            <Table>
              <thead>
                <tr><Th>Field</Th><Th>Value</Th><Th>Confidence</Th><Th className="w-12" /></tr>
              </thead>
              <tbody>
                {detail.data.fields.map((field) => (
                  <FieldRow key={field.id} field={field} canEdit={canEdit} onSaved={refresh} />
                ))}
              </tbody>
            </Table>
          )}
          <p className="text-xs text-muted">{detail.data.notice}</p>
        </div>
      )}
    </Dialog>
  );
}
