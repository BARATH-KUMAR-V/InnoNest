import { useQuery } from "@tanstack/react-query";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Progress, Spinner } from "@/components/ui/feedback";
import { api, ApiError, errorMessage } from "@/lib/api";

interface Risk {
  score: number;
  max_score: number;
  band: string;
  components: { code: string; label: string; points: number; max: number; detail: string }[];
  reason_codes: { code: string; effect: string; detail: string }[];
  scorecard_version: string;
  disclosure: string;
}

const effectTone = { POSITIVE: "ok", NEUTRAL: "neutral", NEGATIVE: "bad" } as const;

export function RiskTab({ applicationId }: { applicationId: number }) {
  const data = useQuery({ queryKey: ["risk", applicationId], queryFn: () => api<Risk>(`/applications/${applicationId}/risk`), retry: false });
  if (data.isLoading) return <Spinner />;
  if (data.error instanceof ApiError && data.error.status === 404) return <Card><EmptyState title="Not scored yet" description="The scorecard runs after the financial assessment." /></Card>;
  if (data.isError || !data.data) return <ErrorNotice message={errorMessage(data.error)} onRetry={() => data.refetch()} />;
  const r = data.data;
  const effects = new Map(r.reason_codes.map((c) => [c.code, c.effect]));
  return (
    <div className="space-y-6">
      <Card>
        <CardBody className="flex flex-wrap items-center gap-8">
          <div>
            <p className="label-sm">Risk score</p>
            <p className="font-display text-4xl font-bold">{r.score}<span className="text-lg font-medium text-muted"> / {r.max_score}</span></p>
          </div>
          <div>
            <p className="label-sm">Band</p>
            <p className="font-display text-4xl font-bold">{r.band}</p>
          </div>
          <p className="max-w-xl text-xs text-muted">{r.disclosure}</p>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="How the score was built" description={`Scorecard ${r.scorecard_version}. Each line is a published, weighted factor.`} />
        <ul>
          {r.components.map((c) => {
            const effect = (effects.get(c.code) ?? "NEUTRAL") as keyof typeof effectTone;
            return (
              <li key={c.code} className="border-b border-line px-5 py-4 last:border-b-0">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-medium">{c.label}</p>
                  <div className="flex items-center gap-2"><Badge tone={effectTone[effect]}>{effect === "POSITIVE" ? "Supports" : effect === "NEGATIVE" ? "Weighs against" : "Neutral"}</Badge><span className="text-sm tabular-nums">{c.points} / {c.max}</span></div>
                </div>
                <Progress className="mt-2" value={(c.points / c.max) * 100} />
                <p className="mt-1.5 text-xs text-muted">{c.detail}</p>
              </li>
            );
          })}
        </ul>
      </Card>
    </div>
  );
}
