import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";
import Nav from "@/components/Nav";
import { AGRO } from "@/constants/testIds";

export default function AgronomistQueue() {
  const { user } = useAuth();
  const nav = useNavigate();
  const { t, i18n } = useTranslation();
  const [items, setItems] = useState([]);

  useEffect(() => {
    if (!user) { nav("/login"); return; }
    if (user.role !== "agronomist" && user.role !== "admin") { nav("/dashboard"); return; }
    api.get("/agronomist/queue").then(r => setItems(r.data));
  }, [user, nav]);

  return (
    <div className="min-h-screen">
      <Nav />
      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="mono text-[10px] uppercase tracking-widest text-secondary">// escalations</div>
        <h1 className="mt-2 font-heading font-bold text-4xl tracking-tight">{t("agro.title")}</h1>
        <p className="mt-1 text-muted-foreground">{t("agro.subtitle")}</p>

        <div className="mt-8 border border-border bg-card divide-y divide-border" data-testid={AGRO.queue}>
          {items.length === 0 && <div className="p-10 text-center text-muted-foreground">{t("agro.empty")}</div>}
          {items.map(d => (
            <div key={d.id} data-testid={AGRO.queueItem} className="p-5 hover:bg-muted/30 transition-colors">
              <div className="flex justify-between flex-wrap gap-2">
                <div>
                  <span className="mono text-[10px] uppercase tracking-widest text-secondary">{d.severity}</span>
                  <span className="ml-3 font-heading font-semibold text-lg">{d.disease}</span>
                </div>
                <span className="mono text-xs text-muted-foreground">{new Date(d.created_at).toLocaleString()}</span>
              </div>
              <div className="mt-2 text-sm text-muted-foreground">
                Confidence {(d.confidence * 100).toFixed(0)}% · Affected {d.affected_area_pct?.toFixed?.(0) || 0}%
              </div>
              <div className="mt-3 text-sm">{i18n.language === "hi" ? d.advisory_hi : d.advisory_en}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
