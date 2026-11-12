import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorNotice, Spinner } from "@/components/ui/feedback";
import { api, errorMessage } from "@/lib/api";
import { cn, titleCase } from "@/lib/utils";

interface GraphNode {
  id: string;
  type: string;
  label: string;
  data: Record<string, unknown>;
}

interface GraphEdge {
  source: string;
  target: string;
  label: string;
}

const columns: string[][] = [["DOCUMENT", "PROVIDER_RESPONSE"], ["APPLICANT", "APPLICATION", "VERIFICATION"], ["CALCULATION", "POLICY"], ["DECISION", "REASON"]];
const fills: Record<string, string> = {
  DOCUMENT: "#F0F5F1", PROVIDER_RESPONSE: "#E4EEF4", APPLICANT: "#FFFFFF", APPLICATION: "#244A36", VERIFICATION: "#FBF1D9", CALCULATION: "#F0F5F1", POLICY: "#FFFFFF", DECISION: "#244A36", REASON: "#F8E6E2",
};
const NODE_W = 190;
const NODE_H = 28;
const GAP = 12;
const COL_GAP = 80;

export function EvidenceTab({ applicationId }: { applicationId: number }) {
  const graph = useQuery({ queryKey: ["evidence", applicationId], queryFn: () => api<{ nodes: GraphNode[]; edges: GraphEdge[] }>(`/applications/${applicationId}/evidence-graph`, { params: { include_fields: false } }) });
  const [selected, setSelected] = useState<string | null>(null);
  const layout = useMemo(() => {
    const positions = new Map<string, { x: number; y: number }>();
    if (!graph.data) return { positions, height: 0 };
    let height = 0;
    columns.forEach((types, c) => {
      let y = 0;
      for (const type of types) {
        for (const node of graph.data.nodes.filter((n) => n.type === type)) {
          positions.set(node.id, { x: c * (NODE_W + COL_GAP), y });
          y += NODE_H + GAP;
        }
        y += GAP;
      }
      height = Math.max(height, y);
    });
    return { positions, height };
  }, [graph.data]);
  if (graph.isLoading) return <Spinner />;
  if (graph.isError || !graph.data) return <ErrorNotice message={errorMessage(graph.error)} onRetry={() => graph.refetch()} />;
  const { nodes, edges } = graph.data;
  if (nodes.length <= 1) return <Card><EmptyState title="No evidence yet" description="Evidence is linked here as documents and verification results arrive." /></Card>;
  const width = columns.length * NODE_W + (columns.length - 1) * COL_GAP;
  const related = new Set<string>();
  if (selected) {
    related.add(selected);
    edges.forEach((e) => {
      if (e.source === selected) related.add(e.target);
      if (e.target === selected) related.add(e.source);
    });
  }
  const chosen = nodes.find((n) => n.id === selected);
  const chosenEdges = edges.filter((e) => e.source === selected || e.target === selected);
  const labelOf = (id: string) => nodes.find((n) => n.id === id)?.label ?? id;
  return (
    <div className="grid gap-6">
      <Card>
        <CardHeader title="Evidence graph" description="From source documents and provider responses, through checks and calculations, to the decision. Select a node to see what it connects to." />
        <CardBody className="overflow-x-auto">
          <div className="mb-2 grid text-[11px] font-medium uppercase tracking-wide text-muted" style={{ width, gridTemplateColumns: `repeat(4, ${NODE_W}px)`, columnGap: COL_GAP }}>
            <span>Evidence</span><span>Parties and checks</span><span>Calculation</span><span>Outcome</span>
          </div>
          <svg width={width} height={layout.height} role="img" aria-label="Evidence graph linking documents, checks, calculations and the decision">
            {edges.map((e, i) => {
              const a = layout.positions.get(e.source);
              const b = layout.positions.get(e.target);
              if (!a || !b) return null;
              const forward = a.x <= b.x;
              const x1 = a.x === b.x ? a.x + NODE_W : forward ? a.x + NODE_W : a.x;
              const x2 = a.x === b.x ? b.x + NODE_W : forward ? b.x : b.x + NODE_W;
              const y1 = a.y + NODE_H / 2;
              const y2 = b.y + NODE_H / 2;
              const mid = (x1 + x2) / 2;
              const active = !selected || (related.has(e.source) && related.has(e.target) && (e.source === selected || e.target === selected));
              const d = a.x === b.x ? `M${x1},${y1} C${x1 + 40},${y1} ${x2 + 40},${y2} ${x2},${y2}` : `M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`;
              return <path key={i} d={d} fill="none" stroke={active ? "#244A36" : "#E2E4DC"} strokeWidth={active && selected ? 1.6 : 1} opacity={selected ? (active ? 0.85 : 0.3) : 0.28} />;
            })}
            {nodes.map((n) => {
              const p = layout.positions.get(n.id);
              if (!p) return null;
              const dark = fills[n.type] === "#244A36";
              const dim = selected && !related.has(n.id);
              return (
                <g key={n.id} transform={`translate(${p.x},${p.y})`} opacity={dim ? 0.35 : 1} onClick={() => setSelected(selected === n.id ? null : n.id)} className="cursor-pointer" role="button" tabIndex={0}
                  onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") setSelected(selected === n.id ? null : n.id); }} aria-label={`${titleCase(n.type)}: ${n.label}`}>
                  <rect width={NODE_W} height={NODE_H} rx={6} fill={fills[n.type]} stroke={selected === n.id ? "#202923" : "#C9CEC3"} strokeWidth={selected === n.id ? 2 : 1} />
                  <text x={10} y={18} fontSize={11.5} fill={dark ? "#FFFFFF" : "#202923"}>{n.label.length > 29 ? `${n.label.slice(0, 28)}…` : n.label}</text>
                  <title>{n.label}</title>
                </g>
              );
            })}
          </svg>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title={chosen ? titleCase(chosen.type) : "Details"} />
        <CardBody className="space-y-3 text-sm">
          {!chosen && <p className="text-muted">Select a node in the graph.</p>}
          {chosen && (
            <>
              <p className="font-medium">{chosen.label}</p>
              <dl className="space-y-1 text-xs">
                {Object.entries(chosen.data).map(([k, v]) => <div key={k}><dt className="inline font-medium">{titleCase(k)}: </dt><dd className={cn("inline break-all", k.includes("hash") || k === "sha256" ? "font-mono" : "text-muted")}>{String(v)}</dd></div>)}
              </dl>
              <div>
                <p className="label-sm mb-1">Connections</p>
                <ul className="space-y-1 text-xs">
                  {chosenEdges.map((e, i) => <li key={i}>{e.source === chosen.id ? `${e.label} → ${labelOf(e.target)}` : `${labelOf(e.source)} → ${e.label}`}</li>)}
                </ul>
              </div>
            </>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
