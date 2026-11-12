import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { BellRing, Play } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/Layout";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Spinner } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { useTitle } from "@/hooks/useTitle";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ApplicationRow, DocRequest, NotificationRecord, Page } from "@/lib/types";
import { dateOnly, dateTime, titleCase } from "@/lib/utils";

interface Config {
  reminder_intervals_hours: number[];
  expiry_days: number;
}

interface Sweep {
  as_of: string;
  actions: { application: string; action: string; number?: number }[];
}

function OpenRequests({ id }: { id: number }) {
  const requests = useQuery({ queryKey: ["requests", String(id)], queryFn: () => api<DocRequest[]>(`/applications/${id}/requests`) });
  const open = (requests.data ?? []).filter((r) => r.status === "OPEN");
  if (requests.isLoading) return <span className="text-muted">Loading</span>;
  if (open.length === 0) return <span className="text-muted">None open</span>;
  return (
    <ul className="space-y-1">
      {open.map((r) => (
        <li key={r.id} className="text-xs">
          <span className="font-medium">{r.title}</span> <span className="text-muted">· {r.reminders_sent} reminder{r.reminders_sent === 1 ? "" : "s"}{r.due_at ? ` · due ${dateOnly(r.due_at)}` : ""}</span>
        </li>
      ))}
    </ul>
  );
}

export default function FollowUp() {
  useTitle("Follow-up monitoring");
  const { user } = useAuth();
  const canOperate = user?.role === "underwriter" || user?.role === "policy_admin";
  const toast = useToast();
  const queryClient = useQueryClient();
  const waiting = useQuery({ queryKey: ["applications", "waiting"], queryFn: () => api<Page<ApplicationRow>>("/applications", { params: { status: "ACTION_REQUIRED,VERIFICATION_PENDING", page_size: 50, sort: "created_at" } }) });
  const config = useQuery({ queryKey: ["follow-up", "config"], queryFn: () => api<Config>("/follow-up/config") });
  const notifications = useQuery({ queryKey: ["notifications", "staff"], queryFn: () => api<Page<NotificationRecord>>("/notifications", { params: { page_size: 10 } }) });
  const [intervals, setIntervals] = useState("");
  const [expiry, setExpiry] = useState("");
  const [advance, setAdvance] = useState("0");
  const [sweep, setSweep] = useState<Sweep | null>(null);

  useEffect(() => {
    if (config.data) {
      setIntervals(config.data.reminder_intervals_hours.join(", "));
      setExpiry(String(config.data.expiry_days));
    }
  }, [config.data]);

  const save = useMutation({
    mutationFn: () => {
      const hours = intervals.split(",").map((v) => Number(v.trim())).filter((v) => v > 0);
      if (hours.length === 0 || hours.some((v) => !Number.isInteger(v))) throw new Error("Enter whole hours separated by commas, for example 24, 72, 120");
      return api<Config>("/follow-up/config", { method: "PUT", body: { reminder_intervals_hours: hours, expiry_days: Number(expiry) } });
    },
    onSuccess: () => { toast.success("Follow-up settings saved"); queryClient.invalidateQueries({ queryKey: ["follow-up"] }); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const run = useMutation({
    mutationFn: () => api<Sweep>("/follow-up/run", { body: { advance_hours: Number(advance) || 0 } }),
    onSuccess: (result) => {
      setSweep(result);
      toast.success(result.actions.length ? `${result.actions.length} follow-up action${result.actions.length === 1 ? "" : "s"} taken` : "Nothing was due");
      queryClient.invalidateQueries();
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <div className="space-y-6">
      <PageHeader title="Follow-up monitoring" description="Applications waiting on the applicant or on a verification source, and the reminders sent. Email and SMS are simulated and never leave this system." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Reminder schedule" description="Applied to every open request. A background job runs this check every few minutes." />
          <CardBody className="space-y-4">
            <Field label="Reminder intervals (hours)" hint="Hours after the previous message. For example 24, 72, 120.">
              <Input value={intervals} onChange={(e) => setIntervals(e.target.value)} disabled={!canOperate} />
            </Field>
            <Field label="Expire after (days)"><Input type="number" value={expiry} onChange={(e) => setExpiry(e.target.value)} disabled={!canOperate} /></Field>
            {canOperate ? <Button loading={save.isPending} onClick={() => save.mutate()}>Save settings</Button> : <p className="text-xs text-muted">Only underwriters and policy administrators can change these settings.</p>}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Run a follow-up check" description="Send due reminders and expire overdue applications now. Advance the clock to see the schedule play out." />
          <CardBody className="space-y-4">
            <Field label="Advance the clock by (hours)" hint="Use 0 for the real time. 30 days is 720 hours."><Input type="number" min={0} value={advance} onChange={(e) => setAdvance(e.target.value)} disabled={!canOperate} /></Field>
            {canOperate && <Button loading={run.isPending} onClick={() => run.mutate()}><Play className="h-4 w-4" /> Run check</Button>}
            {sweep && (
              <div className="rounded-md bg-brand-tint p-3 text-sm">
                <p className="font-medium">Checked as of {dateTime(sweep.as_of)}</p>
                {sweep.actions.length === 0 ? <p className="text-muted">No reminders were due and nothing expired.</p> : (
                  <ul className="mt-1 list-disc pl-5">
                    {sweep.actions.map((a, i) => <li key={i}>{a.application}: {a.action === "REMINDER" ? `reminder ${a.number} sent` : "expired"}</li>)}
                  </ul>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      </div>
      <Card>
        <CardHeader title="Waiting applications" />
        {waiting.isLoading && <Spinner />}
        {waiting.isError && <div className="p-4"><ErrorNotice message={errorMessage(waiting.error)} onRetry={() => waiting.refetch()} /></div>}
        {waiting.data && waiting.data.items.length === 0 && <EmptyState title="Nothing is waiting" description="No application is waiting on an applicant or a verification source." icon={<BellRing className="h-6 w-6" />} />}
        {waiting.data && waiting.data.items.length > 0 && (
          <Table>
            <thead><tr><Th>Reference</Th><Th>Applicant</Th><Th>Status</Th><Th>Open requests</Th></tr></thead>
            <tbody>
              {waiting.data.items.map((row) => (
                <Tr key={row.id}>
                  <Td><Link className="font-medium text-brand hover:underline" to={`/workspace/applications/${row.id}`}>{row.reference}</Link></Td>
                  <Td>{row.applicant_name}</Td>
                  <Td><StatusBadge status={row.status} /></Td>
                  <Td>{row.status === "ACTION_REQUIRED" ? <OpenRequests id={row.id} /> : <span className="text-muted">Waiting on a verification source</span>}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      <Card>
        <CardHeader title="Recent messages" description="Latest notifications across all applicants" />
        {notifications.data && notifications.data.items.length === 0 && <EmptyState title="No messages yet" />}
        {notifications.data && notifications.data.items.length > 0 && (
          <Table>
            <thead><tr><Th>When</Th><Th>Channel</Th><Th>Subject</Th><Th>Delivery</Th></tr></thead>
            <tbody>
              {notifications.data.items.map((n) => (
                <Tr key={n.id}>
                  <Td className="whitespace-nowrap">{dateTime(n.created_at)}</Td>
                  <Td>{titleCase(n.channel)}</Td>
                  <Td>{n.subject}</Td>
                  <Td>{n.simulated ? <Badge tone="info">Simulated, not sent</Badge> : <StatusBadge status={n.delivery_status} />}</Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
    </div>
  );
}
