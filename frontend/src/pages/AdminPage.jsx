import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";
import Nav from "@/components/Nav";
import { ADMIN } from "@/constants/testIds";

export default function AdminPage() {
  const { user } = useAuth();
  const nav = useNavigate();
  const { t } = useTranslation();
  const [pipe, setPipe] = useState(null);
  const [audit, setAudit] = useState([]);

  useEffect(() => {
    if (!user) { nav("/login"); return; }
    if (user.role !== "admin") { nav("/dashboard"); return; }
    const load = async () => {
      const [p, a] = await Promise.all([api.get("/admin/pipeline"), api.get("/admin/audit?limit=50")]);
      setPipe(p.data); setAudit(a.data);
    };
    load();
    const int = setInterval(load, 5000);
    return () => clearInterval(int);
  }, [user, nav]);

  return (
    <div className="min-h-screen">
      <Nav />
      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="mono text-[10px] uppercase tracking-widest text-primary">// ops</div>
        <h1 className="mt-2 font-heading font-bold text-4xl tracking-tight">{t("admin.title")}</h1>
        <p className="mt-1 text-muted-foreground">{t("admin.subtitle")}</p>

        {pipe && (
          <div className="mt-8 grid grid-cols-2 md:grid-cols-5 gap-px bg-border/40" data-testid={ADMIN.pipeline}>
            {[
              { l: "Pending", v: pipe.queue.pending, c: "text-yellow-400" },
              { l: "Processed", v: pipe.queue.processed, c: "text-primary" },
              { l: "Failed", v: pipe.queue.failed, c: "text-destructive" },
              { l: "Workers", v: pipe.queue.workers, c: "text-secondary" },
              { l: "Total jobs", v: pipe.jobs.total, c: "text-foreground" },
            ].map((m, i) => (
              <div key={i} className="bg-card p-5">
                <div className="mono text-[10px] uppercase tracking-widest text-muted-foreground">{m.l}</div>
                <div className={`mt-3 font-heading font-bold text-3xl mono ${m.c}`}>{m.v}</div>
              </div>
            ))}
          </div>
        )}

        <h2 className="mt-10 font-heading text-2xl font-semibold">Audit trail</h2>
        <div className="mt-4 border border-border bg-card divide-y divide-border" data-testid={ADMIN.audit}>
          {audit.map(a => (
            <div key={a.id} className="p-4 flex justify-between text-sm">
              <div>
                <span className="mono text-xs text-primary">{a.action}</span>
                <span className="ml-3 text-muted-foreground">{a.resource}{a.resource_id ? ` · ${a.resource_id.slice(0, 8)}` : ""}</span>
              </div>
              <span className="mono text-xs text-muted-foreground">{new Date(a.created_at).toLocaleString()}</span>
            </div>
          ))}
          {audit.length === 0 && <div className="p-6 text-muted-foreground">No audit entries yet.</div>}
        </div>
      </div>
    </div>
  );
}
