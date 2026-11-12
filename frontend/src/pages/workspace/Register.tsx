import { useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, Download, Search } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/Layout";
import { StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Pagination, Spinner } from "@/components/ui/feedback";
import { Input, Select } from "@/components/ui/form";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { useTitle } from "@/hooks/useTitle";
import { api, download, errorMessage } from "@/lib/api";
import type { ApplicationRow, Page } from "@/lib/types";
import { dateOnly, inr, titleCase } from "@/lib/utils";

const statuses = ["SUBMITTED", "PROCESSING", "ACTION_REQUIRED", "DOCUMENTS_RECEIVED", "VERIFICATION_PENDING", "REFERRED", "APPROVED", "REJECTED", "EXPIRED", "WITHDRAWN", "DRAFT"];

export default function Register() {
  useTitle("Application register");
  const toast = useToast();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [product, setProduct] = useState("");
  const [sort, setSort] = useState("created_at");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [page, setPage] = useState(1);
  const list = useQuery({
    queryKey: ["applications", "register", q, status, product, sort, order, page],
    queryFn: () => api<Page<ApplicationRow>>("/applications", { params: { q, status, product, sort, order, page, page_size: 15 } }),
    placeholderData: (previous) => previous,
  });
  const toggle = (column: string) => {
    if (sort === column) setOrder(order === "asc" ? "desc" : "asc");
    else { setSort(column); setOrder("desc"); }
    setPage(1);
  };
  const header = (column: string, label: string) => (
    <Th>
      <button className="inline-flex items-center gap-1 uppercase tracking-wide" onClick={() => toggle(column)} aria-label={`Sort by ${label}`}>
        {label}{sort === column && (order === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />)}
      </button>
    </Th>
  );
  const exportCsv = async () => {
    try {
      await download("/reports/applications.csv", "innonest-applications.csv", { status, product });
      toast.success("Register exported");
    } catch (error) {
      toast.error(errorMessage(error));
    }
  };
  const filtered = Boolean(q || status || product);
  return (
    <div>
      <PageHeader title="Application register" description="Every application, with its current status." actions={<Button variant="outline" onClick={exportCsv}><Download className="h-4 w-4" /> Export CSV</Button>} />
      <Card>
        <div className="flex flex-wrap gap-3 border-b border-line p-4">
          <div className="relative min-w-[220px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted" />
            <Input className="pl-9" placeholder="Search by reference, applicant or city" aria-label="Search the register" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
          </div>
          <Select className="w-52" aria-label="Filter by status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
            <option value="">All statuses</option>
            {statuses.map((s) => <option key={s} value={s}>{titleCase(s)}</option>)}
          </Select>
          <Select className="w-44" aria-label="Filter by product" value={product} onChange={(e) => { setProduct(e.target.value); setPage(1); }}>
            <option value="">All products</option>
            <option value="HOME_LOAN">Home Loan</option>
            <option value="LAP">Loan Against Property</option>
          </Select>
        </div>
        {list.isLoading && <Spinner />}
        {list.isError && <div className="p-4"><ErrorNotice message={errorMessage(list.error)} onRetry={() => list.refetch()} /></div>}
        {list.data && list.data.items.length === 0 && <EmptyState title={filtered ? "No applications match" : "The register is empty"} description={filtered ? "Change or clear the filters." : "Applications appear here once applicants create them."} />}
        {list.data && list.data.items.length > 0 && (
          <>
            <Table>
              <thead>
                <tr>{header("reference", "Reference")}<Th>Applicant</Th><Th>Product</Th>{header("loan_amount", "Loan amount")}<Th>City</Th><Th>Policy</Th>{header("status", "Status")}{header("created_at", "Created")}</tr>
              </thead>
              <tbody>
                {list.data.items.map((row) => (
                  <Tr key={row.id} className="hover:bg-brand-tint">
                    <Td><Link className="font-medium text-brand hover:underline" to={`/workspace/applications/${row.id}`}>{row.reference}</Link></Td>
                    <Td>{row.applicant_name ?? "-"}<div className="text-xs text-muted">{titleCase(row.employment_type)}</div></Td>
                    <Td>{titleCase(row.product)}</Td>
                    <Td>{inr(row.loan_amount)}</Td>
                    <Td>{row.property_city}</Td>
                    <Td>{titleCase(row.policy_key)}</Td>
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
