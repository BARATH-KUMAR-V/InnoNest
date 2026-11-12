import { useQuery } from "@tanstack/react-query";
import { Download, ShieldCheck } from "lucide-react";
import { Fragment, useState } from "react";
import { PageHeader } from "@/components/Layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Pagination, Spinner } from "@/components/ui/feedback";
import { Input } from "@/components/ui/form";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { useTitle } from "@/hooks/useTitle";
import { api, download, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { AuditEvent, Page } from "@/lib/types";
import { dateTime } from "@/lib/utils";

interface Verify {
  intact: boolean;
  checked: number;
  broken_at: number | null;
}

export default function Audit() {
  useTitle("Audit history");
  const { user } = useAuth();
  const toast = useToast();
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<number | null>(null);
  const [verify, setVerify] = useState<Verify | null>(null);
  const [verifying, setVerifying] = useState(false);
  const list = useQuery({ queryKey: ["audit", action, actor, page], queryFn: () => api<Page<AuditEvent>>("/audit", { params: { action, actor, page, page_size: 20 } }), placeholderData: (p) => p });
  const check = async () => {
    setVerifying(true);
    try {
      const result = await api<Verify>("/audit/verify");
      setVerify(result);
      if (result.intact) toast.success("The audit chain is intact");
      else toast.error("The audit chain has been altered");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setVerifying(false);
    }
  };
  const exportCsv = async () => {
    try {
      await download("/reports/audit.csv", "innonest-audit.csv");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };
  const canExport = user?.role === "auditor" || user?.role === "underwriter";
  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit history"
        description="Every action is recorded with the actor and linked to the previous record by a hash, so edits can be detected."
        actions={
          <>
            <Button variant="outline" loading={verifying} onClick={check}><ShieldCheck className="h-4 w-4" /> Verify chain</Button>
            {canExport && <Button variant="outline" onClick={exportCsv}><Download className="h-4 w-4" /> Export CSV</Button>}
          </>
        }
      />
      {verify && (
        <div className={`rounded-lg border p-4 text-sm ${verify.intact ? "border-brand/30 bg-brand-soft" : "border-bad/30 bg-bad-soft"}`} role="status">
          {verify.intact ? `All ${verify.checked} records link correctly. No record has been changed or removed.` : `The chain breaks at record ${verify.broken_at}. Records from that point cannot be trusted.`}
        </div>
      )}
      <Card>
        <div className="flex flex-wrap gap-3 border-b border-line p-4">
          <Input className="w-56" placeholder="Action, for example decision" aria-label="Filter by action" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }} />
          <Input className="w-56" placeholder="Actor email" aria-label="Filter by actor" value={actor} onChange={(e) => { setActor(e.target.value); setPage(1); }} />
        </div>
        {list.isLoading && <Spinner />}
        {list.isError && <div className="p-4"><ErrorNotice message={errorMessage(list.error)} onRetry={() => list.refetch()} /></div>}
        {list.data && list.data.items.length === 0 && <EmptyState title="No records match" description="Change or clear the filters." />}
        {list.data && list.data.items.length > 0 && (
          <>
            <Table>
              <thead><tr><Th>#</Th><Th>When</Th><Th>Actor</Th><Th>Action</Th><Th>Application</Th><Th>Hash</Th></tr></thead>
              <tbody>
                {list.data.items.map((e) => (
                  <Fragment key={e.id}>
                    <Tr className="cursor-pointer hover:bg-brand-tint" onClick={() => setOpen(open === e.id ? null : e.id)}>
                      <Td>{e.id}</Td>
                      <Td className="whitespace-nowrap">{dateTime(e.created_at)}</Td>
                      <Td>{e.actor}<div className="text-xs text-muted">{e.actor_role}</div></Td>
                      <Td><Badge>{e.action}</Badge></Td>
                      <Td>{e.application_id ?? "-"}</Td>
                      <Td className="font-mono text-xs text-muted">{e.hash.slice(0, 10)}</Td>
                    </Tr>
                    {open === e.id && (
                      <tr>
                        <td colSpan={6} className="border-b border-line bg-brand-tint px-4 py-3">
                          <pre className="overflow-x-auto whitespace-pre-wrap text-xs">{JSON.stringify(e.details, null, 2)}</pre>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </Table>
            <Pagination page={list.data.page} pageSize={list.data.page_size} total={list.data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
