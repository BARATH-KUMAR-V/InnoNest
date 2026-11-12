import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, CheckCheck, Mail, MessageSquare } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { PageHeader } from "@/components/Layout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Pagination, Spinner } from "@/components/ui/feedback";
import { Select } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { useTitle } from "@/hooks/useTitle";
import { api, errorMessage } from "@/lib/api";
import type { NotificationRecord, Page } from "@/lib/types";
import { cn, dateTime, titleCase } from "@/lib/utils";

const icons: Record<string, JSX.Element> = { IN_APP: <Bell className="h-4 w-4" />, EMAIL: <Mail className="h-4 w-4" />, SMS: <MessageSquare className="h-4 w-4" /> };

export default function Notifications() {
  useTitle("Notifications");
  const queryClient = useQueryClient();
  const toast = useToast();
  const [channel, setChannel] = useState("");
  const [page, setPage] = useState(1);
  const list = useQuery({
    queryKey: ["notifications", "list", channel, page],
    queryFn: () => api<Page<NotificationRecord> & { unread_in_app: number }>("/notifications", { params: { channel, page, page_size: 10 } }),
    placeholderData: (previous) => previous,
  });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["notifications"] });
  const read = useMutation({ mutationFn: (id: number) => api(`/notifications/${id}/read`, { method: "POST" }), onSuccess: refresh, onError: (e) => toast.error(errorMessage(e)) });
  const readAll = useMutation({
    mutationFn: () => api<{ marked: number }>("/notifications/read-all", { method: "POST" }),
    onSuccess: (result) => { toast.success(result.marked ? `${result.marked} marked as read` : "Nothing to mark"); refresh(); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title="Notifications"
        description="Updates and reminders about your applications. Email and SMS messages are simulated in this build and are not sent."
        actions={<Button variant="outline" loading={readAll.isPending} onClick={() => readAll.mutate()}><CheckCheck className="h-4 w-4" /> Mark all as read</Button>}
      />
      <div className="mb-4 w-48">
        <Select aria-label="Filter by channel" value={channel} onChange={(e) => { setChannel(e.target.value); setPage(1); }}>
          <option value="">All channels</option>
          <option value="IN_APP">In app</option>
          <option value="EMAIL">Email (simulated)</option>
          <option value="SMS">SMS (simulated)</option>
        </Select>
      </div>
      <Card>
        {list.isLoading && <Spinner />}
        {list.isError && <div className="p-4"><ErrorNotice message={errorMessage(list.error)} onRetry={() => list.refetch()} /></div>}
        {list.data && list.data.items.length === 0 && <EmptyState title="No notifications" description="When we need something from you or reach a decision, you will see it here." />}
        {list.data && list.data.items.length > 0 && (
          <>
            <ul>
              {list.data.items.map((n) => {
                const unread = n.channel === "IN_APP" && !n.read_at;
                return (
                  <li key={n.id} className={cn("flex gap-3 border-b border-line px-4 py-4 last:border-b-0", unread && "bg-brand-tint")}>
                    <span className="mt-0.5 text-brand">{icons[n.channel]}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className={cn("text-sm", unread ? "font-semibold" : "font-medium")}>{n.subject}</p>
                        {n.simulated && <Badge tone="info">Simulated, not sent</Badge>}
                        <Badge>{titleCase(n.channel)}</Badge>
                      </div>
                      <p className="mt-1 whitespace-pre-line text-sm text-muted">{n.body}</p>
                      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted">
                        <span>{dateTime(n.created_at)}</span>
                        {n.application_id && <Link className="font-medium text-brand hover:underline" to={`/portal/applications/${n.application_id}`}>Open application</Link>}
                        {unread && <button className="font-medium text-brand hover:underline" onClick={() => read.mutate(n.id)}>Mark as read</button>}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
            <Pagination page={list.data.page} pageSize={list.data.page_size} total={list.data.total} onPage={setPage} />
          </>
        )}
      </Card>
    </div>
  );
}
