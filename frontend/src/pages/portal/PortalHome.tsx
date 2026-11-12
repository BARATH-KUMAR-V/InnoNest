import { useQuery } from "@tanstack/react-query";
import { Plus, Search } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/Layout";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Pagination, Spinner } from "@/components/ui/feedback";
import { Input, Select } from "@/components/ui/form";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useTitle } from "@/hooks/useTitle";
import { api, errorMessage } from "@/lib/api";
import type { ApplicationRow, Page } from "@/lib/types";
import { dateOnly, inr, titleCase } from "@/lib/utils";

const statuses = ["DRAFT", "SUBMITTED", "PROCESSING", "ACTION_REQUIRED", "DOCUMENTS_RECEIVED", "VERIFICATION_PENDING", "REFERRED", "APPROVED", "REJECTED", "EXPIRED", "WITHDRAWN"];

export default function PortalHome() {
  useTitle("My applications");
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const list = useQuery({
    queryKey: ["applications", "mine", q, status, page],
    queryFn: () => api<Page<ApplicationRow>>("/applications", { params: { q, status, page, page_size: 10 } }),
    placeholderData: (previous) => previous,
  });
  const filtered = Boolean(q || status);
  return (
    <div>
      <PageHeader
        title="My applications"
        description="Track your home loan and loan against property applications, and see what we still need from you."
        actions={<Button onClick={() => navigate("/portal/applications/new")}><Plus className="h-4 w-4" /> New application</Button>}
      />
      <Card>
        <div className="flex flex-wrap gap-3 border-b border-line p-4">
          <div className="relative min-w-[200px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted" />
            <Input className="pl-9" placeholder="Search by reference or city" aria-label="Search applications" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
          </div>
          <Select className="w-52" aria-label="Filter by status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            {statuses.map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
          </Select>
        </div>
        {list.isLoading && <Spinner />}
        {list.isError && <div className="p-4"><ErrorNotice message={errorMessage(list.error)} onRetry={() => list.refetch()} /></div>}
        {list.data && list.data.items.length === 0 && (
          <EmptyState
            title={filtered ? "No applications match" : "You have no applications yet"}
            description={filtered ? "Try a different search or clear the status filter." : "Start an application. You can save a draft and add documents later."}
            action={!filtered ? <Button onClick={() => navigate("/portal/applications/new")}><Plus className="h-4 w-4" /> Start an application</Button> : undefined}
          />
        )}
        {list.data && list.data.items.length > 0 && (
          <>
            <Table>
              <thead>
                <tr><Th>Reference</Th><Th>Product</Th><Th>Loan amount</Th><Th>Property city</Th><Th>Status</Th><Th>Created</Th></tr>
              </thead>
              <tbody>
                {list.data.items.map((row) => (
                  <Tr key={row.id} className="hover:bg-brand-tint">
                    <Td><Link className="font-medium text-brand hover:underline" to={`/portal/applications/${row.id}`}>{row.reference}</Link></Td>
                    <Td>{titleCase(row.product)}</Td>
                    <Td>{inr(row.loan_amount)}</Td>
                    <Td>{row.property_city}</Td>
                    <Td><StatusBadge status={row.status} /></Td>
                    <Td>{dateOnly(row.created_at)}</Td>
                  </Tr>
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
