import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { PageHeader } from "@/components/Layout";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Spinner, Stat } from "@/components/ui/feedback";
import { useTitle } from "@/hooks/useTitle";
import { api, errorMessage } from "@/lib/api";
import { dateTime, pct, titleCase } from "@/lib/utils";

interface Dashboard {
  total: number;
  approved: number;
  rejected: number;
  referred: number;
  action_required: number;
  verification_pending: number;
  draft: number;
  approval_rate: number;
  avg_days_to_decision: number | null;
  status_breakdown: { status: string; count: number }[];
  product_distribution: { product: string; count: number }[];
  outcomes_by_product: { product: string; APPROVED: number; REJECTED: number; REFERRED: number }[];
  applications_per_day: { date: string; count: number }[];
  recent_activity: { id: number; action: string; application_id: number; reference: string | null; actor: string; at: string }[];
}

const axis = { tickLine: false, axisLine: false, fontSize: 12, stroke: "#5C675F" };

export default function Dashboard() {
  useTitle("Dashboard");
  const data = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dashboard>("/reports/dashboard") });
  if (data.isLoading) return <Spinner />;
  if (data.isError || !data.data) return <ErrorNotice message={errorMessage(data.error)} onRetry={() => data.refetch()} />;
  const d = data.data;
  const statusData = d.status_breakdown.filter((s) => s.count > 0).map((s) => ({ ...s, label: titleCase(s.status) }));
  const outcomes = d.outcomes_by_product.map((o) => ({ product: titleCase(o.product), Approved: o.APPROVED, Rejected: o.REJECTED, Referred: o.REFERRED }));
  return (
    <div className="space-y-6">
      <PageHeader title="Dashboard" description="Live figures from the application register." />
      <Card>
        <CardBody className="grid grid-cols-2 gap-6 md:grid-cols-4 xl:grid-cols-7">
          <Stat label="Applications" value={d.total} />
          <Stat label="Approved" value={d.approved} tone="ok" />
          <Stat label="Rejected" value={d.rejected} tone="bad" />
          <Stat label="Referred" value={d.referred} tone="warn" />
          <Stat label="Action required" value={d.action_required} tone="warn" hint="Waiting on applicants" />
          <Stat label="Verification pending" value={d.verification_pending} hint="Waiting on sources" />
          <Stat label="Approval rate" value={d.total - d.draft > 0 ? pct(d.approval_rate, 0) : "-"} hint={d.avg_days_to_decision === null ? "Of decided applications" : d.avg_days_to_decision < 1 ? "Decided within a day on average" : `${d.avg_days_to_decision} days to decide on average`} />
        </CardBody>
      </Card>
      {d.total === 0 ? (
        <Card><EmptyState title="No applications yet" description="Figures appear here once applicants start submitting." /></Card>
      ) : (
        <>
          <div className="grid gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader title="Applications by status" />
              <CardBody>
                <div className="h-72" role="img" aria-label="Number of applications in each status">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={statusData} layout="vertical" margin={{ left: 40 }}>
                      <CartesianGrid stroke="#E2E4DC" horizontal={false} />
                      <XAxis type="number" allowDecimals={false} {...axis} />
                      <YAxis type="category" dataKey="label" width={150} {...axis} />
                      <Tooltip cursor={{ fill: "#F0F5F1" }} />
                      <Bar dataKey="count" name="Applications" fill="#244A36" radius={[0, 4, 4, 0]} barSize={16} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Outcomes by product" description="Decided and referred applications" />
              <CardBody>
                <div className="h-72" role="img" aria-label="Approved, rejected and referred applications by product">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={outcomes}>
                      <CartesianGrid stroke="#E2E4DC" vertical={false} />
                      <XAxis dataKey="product" {...axis} />
                      <YAxis allowDecimals={false} {...axis} width={30} />
                      <Tooltip cursor={{ fill: "#F0F5F1" }} />
                      <Legend iconType="circle" />
                      <Bar dataKey="Approved" stackId="a" fill="#244A36" barSize={40} />
                      <Bar dataKey="Referred" stackId="a" fill="#C9A24B" />
                      <Bar dataKey="Rejected" stackId="a" fill="#A63A2B" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardBody>
            </Card>
          </div>
          <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
            <Card>
              <CardHeader title="Applications created, last 30 days" />
              <CardBody>
                {d.applications_per_day.length === 0 ? <p className="text-sm text-muted">No applications were created in the last 30 days.</p> : (
                  <div className="h-60" role="img" aria-label="Applications created per day">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={d.applications_per_day}>
                        <CartesianGrid stroke="#E2E4DC" vertical={false} />
                        <XAxis dataKey="date" {...axis} />
                        <YAxis allowDecimals={false} {...axis} width={30} />
                        <Tooltip />
                        <Line type="monotone" dataKey="count" name="Created" stroke="#244A36" strokeWidth={2} dot />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Recent activity" />
              <ul className="max-h-72 overflow-y-auto">
                {d.recent_activity.map((e) => (
                  <li key={e.id} className="border-b border-line px-5 py-3 text-sm last:border-b-0">
                    <p className="font-medium">{titleCase(e.action.replace(/\./g, " "))}</p>
                    <p className="text-xs text-muted">
                      {e.reference && <Link className="text-brand hover:underline" to={`/workspace/applications/${e.application_id}`}>{e.reference}</Link>} · {e.actor} · {dateTime(e.at)}
                    </p>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
