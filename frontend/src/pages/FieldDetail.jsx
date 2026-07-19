import React, { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";
import Nav from "@/components/Nav";
import FieldMap from "@/components/FieldMap";
import { FIELD, DASH } from "@/constants/testIds";
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { Loader2 } from "lucide-react";

const SEV_COLOR = {
  low: "text-primary", moderate: "text-yellow-400",
  high: "text-secondary", critical: "text-destructive",
};

export default function FieldDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const { t, i18n } = useTranslation();
  const [field, setField] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    if (!user) { nav("/login"); return; }
    (async () => {
      const [f, h] = await Promise.all([
        api.get(`/fields/${id}`),
        api.get(`/fields/${id}/history`),
      ]);
      setField(f.data);
      setHistory(h.data);
    })();
  }, [id, user, nav]);

  if (!field) return <div className="min-h-screen"><Nav /><div className="mx-auto max-w-7xl px-6 py-16"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div></div>;

  const trend = [...history].reverse().map((d, i) => ({
    day: (d.created_at || "").slice(5, 10),
    health: Math.max(0, 100 - (d.affected_area_pct || 0)),
    confidence: (d.confidence || 0) * 100,
  }));

  return (
    <div className="min-h-screen" data-testid={FIELD.detail}>
      <Nav />
      <div className="mx-auto max-w-7xl px-6 py-10">
        <button onClick={() => nav(-1)} className="mono text-xs text-muted-foreground hover:text-primary transition-colors">← back</button>
        <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="mono text-[10px] uppercase tracking-widest text-primary">// field · {field.region}</div>
            <h1 className="mt-2 font-heading font-bold text-4xl tracking-tight">{field.name}</h1>
            <p className="mt-1 text-muted-foreground capitalize">{field.crop} · {field.area_hectares} ha · lat {field.location.coordinates[1]}, lng {field.location.coordinates[0]}</p>
          </div>
          <div className="text-right">
            <div className="mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("dash.health")}</div>
            <div className="font-heading font-bold text-5xl text-primary">{Math.round(field.health_score)}</div>
          </div>
        </div>

        <div className="mt-8 grid lg:grid-cols-2 gap-6">
          <div className="border border-border bg-card p-6">
            <div className="mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("dash.trend")}</div>
            <div className="h-64 mt-3">
              <ResponsiveContainer>
                <LineChart data={trend}>
                  <CartesianGrid stroke="hsl(144 20% 12%)" strokeDasharray="3 3" />
                  <XAxis dataKey="day" stroke="hsl(144 10% 65%)" fontSize={11} />
                  <YAxis stroke="hsl(144 10% 65%)" fontSize={11} />
                  <Tooltip contentStyle={{ background: "hsl(144 24% 7%)", border: "1px solid hsl(144 20% 12%)" }} />
                  <Line type="monotone" dataKey="health" stroke="hsl(142 76% 55%)" strokeWidth={2} dot={false} />
                  <Line type="monotone" dataKey="confidence" stroke="hsl(25 95% 53%)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div>
            <div className="mono text-[10px] uppercase tracking-widest text-muted-foreground mb-2">field boundary</div>
            <FieldMap fields={[field]} height={296} />
          </div>
        </div>

        <h2 className="mt-10 font-heading text-2xl font-semibold">{t("dash.history")}</h2>
        <div className="mt-4 border border-border bg-card divide-y divide-border" data-testid={FIELD.history}>
          {history.length === 0 && <div className="p-6 text-muted-foreground">No detections yet.</div>}
          {history.map(d => (
            <div key={d.id} data-testid={FIELD.historyItem} className="p-5 hover:bg-muted/30 transition-colors">
              <div className="flex justify-between flex-wrap gap-2">
                <div>
                  <span className={`mono text-[10px] uppercase tracking-widest ${SEV_COLOR[d.severity] || "text-foreground"}`}>{d.severity}</span>
                  <span className="ml-3 font-heading font-semibold text-lg">{d.disease}</span>
                </div>
                <span className="mono text-xs text-muted-foreground">{new Date(d.created_at).toLocaleString()}</span>
              </div>
              <div className="mt-2 text-sm text-muted-foreground">
                Confidence {(d.confidence * 100).toFixed(0)}% · Affected {d.affected_area_pct?.toFixed?.(0) || 0}%
              </div>
              <div className="mt-3 text-sm leading-relaxed">{i18n.language === "hi" ? d.advisory_hi : d.advisory_en}</div>
              {d.reasoning_trace?.length > 0 && (
                <details className="mt-3">
                  <summary className="cursor-pointer mono text-xs text-primary uppercase tracking-widest">{t("dash.reasoning")}</summary>
                  <pre className="mt-2 text-xs bg-background border border-border p-3 overflow-x-auto rounded-sm">
                    {JSON.stringify(d.reasoning_trace, null, 2)}
                  </pre>
                </details>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
