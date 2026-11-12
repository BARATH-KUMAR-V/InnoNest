import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/Layout";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorNotice, Spinner } from "@/components/ui/feedback";
import { Table, Td, Th, Tr } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { useTitle } from "@/hooks/useTitle";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Integration {
  key: string;
  name: string;
  mode: string;
  mode_note: string;
  production_route: string;
  needs_consent: boolean;
  simulated_outage: boolean;
  live: boolean;
}

export default function Integrations() {
  useTitle("Integrations");
  const { user } = useAuth();
  const canOperate = user?.role === "underwriter" || user?.role === "policy_admin";
  const toast = useToast();
  const queryClient = useQueryClient();
  const list = useQuery({ queryKey: ["integrations"], queryFn: () => api<Integration[]>("/integrations") });
  const outage = useMutation({
    mutationFn: (v: { key: string; down: boolean }) => api(`/integrations/${v.key}/outage`, { body: { down: v.down } }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["integrations"] }); toast.success("Simulated outage updated"); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <div className="space-y-6">
      <PageHeader title="Integrations" description="Every verification source runs through an adapter. No adapter in this build is connected to a live partner, and none reports a live result." />
      <Card>
        {list.isLoading && <Spinner />}
        {list.isError && <div className="p-4"><ErrorNotice message={errorMessage(list.error)} onRetry={() => list.refetch()} /></div>}
        {list.data && (
          <Table>
            <thead><tr><Th>Source</Th><Th>Mode</Th><Th>What the mode means</Th><Th>Production route</Th><Th>Simulated outage</Th></tr></thead>
            <tbody>
              {list.data.map((i) => (
                <Tr key={i.key}>
                  <Td className="font-medium">{i.name}{i.needs_consent && <div className="text-xs font-normal text-muted">Needs applicant consent</div>}</Td>
                  <Td><StatusBadge status={i.mode} /></Td>
                  <Td className="max-w-[260px] text-muted">{i.mode_note}</Td>
                  <Td className="max-w-[260px] text-muted">{i.production_route}</Td>
                  <Td>
                    {i.simulated_outage && <Badge tone="bad" className="mr-2">Down</Badge>}
                    {canOperate ? (
                      <Button variant="outline" size="sm" loading={outage.isPending && outage.variables?.key === i.key} onClick={() => outage.mutate({ key: i.key, down: !i.simulated_outage })}>
                        {i.simulated_outage ? "Restore" : "Simulate outage"}
                      </Button>
                    ) : !i.simulated_outage && <span className="text-muted">Up</span>}
                  </Td>
                </Tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>
      <p className="text-xs text-muted">A simulated outage on a critical source holds new applications in verification pending until the source is restored and verification is retried.</p>
    </div>
  );
}
