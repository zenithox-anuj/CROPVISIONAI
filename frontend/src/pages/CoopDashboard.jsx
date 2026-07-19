import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";
import Nav from "@/components/Nav";
import FieldMap from "@/components/FieldMap";
import { COOP } from "@/constants/testIds";
import { motion } from "framer-motion";
import { Users, Wheat, Ruler, Activity, Loader2 } from "lucide-react";
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";

const STATUS_COLOR = {
  healthy: "text-primary", monitoring: "text-yellow-400",
  diseased: "text-secondary", critical: "text-destructive",
};

export default function CoopDashboard() {
  const { user, loading } = useAuth();
  const nav = useNavigate();
  const { t, i18n } = useTranslation();
  const [data, setData] = useState(null);
  const [fields, setFields] = useState([]);

  useEffect(() => {
    if (loading) return;
    if (!user) { nav("/login"); return; }
    if (user.role !== "coop_admin" && user.role !== "admin") { nav("/dashboard"); return; }
    const load = async () => {
      const [d, f] = await Promise.all([api.get("/coop/dashboard"), api.get("/fields")]);
      setData(d.data); setFields(f.data);
    };
    load();
  }, [user, loading, nav]);

  if (!data) return (
    <div className="min-h-screen"><Nav />
      <div className="mx-auto max-w-7xl px-6 py-16"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
    </div>
  );

  const diseaseData = data.top_diseases.map(([name, count]) => ({ name: name.length > 14 ? name.slice(0, 14) + "…" : name, count }));

  return (
    <div className="min-h-screen" data-testid={COOP.root}>
      <Nav />
      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="mono text-[10px] uppercase tracking-widest text-primary">// cooperative · {data.cooperative?.region}</div>
        <h1 className="mt-2 font-heading font-bold text-4xl tracking-tight">{data.cooperative?.name || t("coop.title")}</h1>
        <p className="mt-1 text-muted-foreground">{t("coop.subtitle")}</p>

        <div className="mt-8 grid grid-cols-2 md:grid-cols-5 gap-px bg-border/40" data-testid={COOP.totals}>
          {[
            { Icon: Users, l: t("coop.farmers"), v: data.totals.farmers, c: "text-primary" },
            { Icon: Wheat, l: t("coop.fields"), v: data.totals.fields, c: "text-primary" },
            { Icon: Ruler, l: t("coop.hectares"), v: data.totals.total_hectares, c: "text-secondary" },
            { Icon: Activity, l: t("coop.avgHealth"), v: `${data.totals.avg_health}%`, c: "text-primary" },
            { Icon: Activity, l: t("coop.detections"), v: data.totals.detections_recent, c: "text-yellow-400" },
          ].map((m, i) => (
            <motion.div
              key={i} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
              className="bg-card p-5">
              <div className="flex items-center justify-between">
                <span className="mono text-[10px] tracking-widest uppercase text-muted-foreground">{m.l}</span>
                <m.Icon className={`w-4 h-4 ${m.c}`} />
              </div>
              <div className={`mt-3 font-heading font-bold text-3xl mono ${m.c}`}>{m.v}</div>
            </motion.div>
          ))}
        </div>

        <div className="mt-8 grid lg:grid-cols-2 gap-6">
          <div className="border border-border bg-card p-6">
            <div className="mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("coop.topDiseases")}</div>
            <div className="mt-4 h-64" data-testid={COOP.topDiseases}>
              <ResponsiveContainer>
                <BarChart data={diseaseData}>
                  <CartesianGrid stroke="hsl(144 20% 12%)" strokeDasharray="3 3" />
                  <XAxis dataKey="name" stroke="hsl(144 10% 65%)" fontSize={11} interval={0} angle={-15} textAnchor="end" height={60} />
                  <YAxis stroke="hsl(144 10% 65%)" fontSize={11} />
                  <Tooltip contentStyle={{ background: "hsl(144 24% 7%)", border: "1px solid hsl(144 20% 12%)" }} />
                  <Bar dataKey="count" fill="hsl(142 76% 55%)" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="border border-border bg-card p-6">
            <div className="mono text-[10px] uppercase tracking-widest text-muted-foreground">{t("coop.statusBreakdown")}</div>
            <div className="mt-4 space-y-3">
              {Object.entries(data.by_status).map(([status, count]) => (
                <div key={status} className="flex items-center justify-between">
                  <span className={`mono text-xs uppercase tracking-widest ${STATUS_COLOR[status] || "text-foreground"}`}>{status}</span>
                  <div className="flex items-center gap-3">
                    <div className="w-40 h-2 bg-muted rounded-sm overflow-hidden">
                      <div className={`h-full ${STATUS_COLOR[status]?.replace("text-", "bg-") || "bg-primary"}`}
                           style={{ width: `${Math.min(100, (count / data.totals.fields) * 100)}%` }} />
                    </div>
                    <span className="mono text-sm w-8 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <h2 className="mt-10 font-heading text-2xl font-semibold">{t("map.title")}</h2>
        <div className="mt-4">
          <FieldMap fields={fields} height={480} />
        </div>

        <h2 className="mt-10 font-heading text-2xl font-semibold">Growers</h2>
        <div className="mt-4 border border-border bg-card divide-y divide-border">
          {data.farmers.map(f => (
            <div key={f.id} data-testid={COOP.farmerRow} className="p-4 flex justify-between items-center">
              <div>
                <div className="font-semibold">{f.name}</div>
                <div className="mono text-xs text-muted-foreground">{f.email} · {f.phone || "—"}</div>
              </div>
              <span className="mono text-[10px] uppercase tracking-widest text-muted-foreground">{f.language}</span>
            </div>
          ))}
          {data.farmers.length === 0 && <div className="p-6 text-muted-foreground">No growers linked yet.</div>}
        </div>

        <h2 className="mt-10 font-heading text-2xl font-semibold">{t("coop.recentActivity")}</h2>
        <div className="mt-4 border border-border bg-card divide-y divide-border">
          {data.recent_detections.map(d => (
            <div key={d.id} data-testid={COOP.detectionItem} className="p-4">
              <div className="flex justify-between flex-wrap gap-2">
                <div>
                  <span className={`mono text-[10px] uppercase tracking-widest ${STATUS_COLOR[d.severity === "critical" || d.severity === "high" ? "critical" : "healthy"]}`}>{d.severity}</span>
                  <span className="ml-3 font-heading font-semibold">{d.disease}</span>
                </div>
                <span className="mono text-xs text-muted-foreground">{new Date(d.created_at).toLocaleString()}</span>
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                {i18n.language === "hi" ? d.advisory_hi : d.advisory_en}
              </div>
            </div>
          ))}
          {data.recent_detections.length === 0 && <div className="p-6 text-muted-foreground">{t("coop.empty")}</div>}
        </div>
      </div>
    </div>
  );
}
