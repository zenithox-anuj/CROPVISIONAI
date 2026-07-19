import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";
import Nav from "@/components/Nav";
import { DASH } from "@/constants/testIds";

const SEV_COLOR = {
  low: "border-primary/40 text-primary",
  moderate: "border-yellow-400/40 text-yellow-400",
  high: "border-secondary/40 text-secondary",
  critical: "border-destructive/50 text-destructive",
};

export default function AlertsPage() {
  const { user } = useAuth();
  const nav = useNavigate();
  const { t, i18n } = useTranslation();
  const [alerts, setAlerts] = useState([]);

  useEffect(() => {
    if (!user) { nav("/login"); return; }
    api.get("/alerts?limit=200").then(r => setAlerts(r.data));
  }, [user, nav]);

  return (
    <div className="min-h-screen">
      <Nav />
      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="mono text-[10px] uppercase tracking-widest text-primary">// feed</div>
        <h1 className="mt-2 font-heading font-bold text-4xl tracking-tight">{t("nav.alerts")}</h1>

        <div className="mt-8 space-y-2">
          {alerts.map(a => (
            <div key={a.id} data-testid={DASH.alertItem}
              className={`border-l-2 bg-card p-4 ${SEV_COLOR[a.severity] || "border-border"}`}>
              <div className="flex justify-between flex-wrap gap-2">
                <span className="mono text-[10px] uppercase tracking-widest">{t(`dash.severity_${a.severity}`)}</span>
                <span className="mono text-[10px] text-muted-foreground">{new Date(a.created_at).toLocaleString()}</span>
              </div>
              <div className="mt-2 text-sm">{i18n.language === "hi" ? a.message_hi : a.message_en}</div>
              <div className="mt-1 mono text-[10px] text-muted-foreground uppercase tracking-widest">channel: {a.channel} · delivered: {a.delivered ? "yes" : "no"}</div>
            </div>
          ))}
          {alerts.length === 0 && <div className="text-muted-foreground p-6">{t("dash.alertEmpty")}</div>}
        </div>
      </div>
    </div>
  );
}
