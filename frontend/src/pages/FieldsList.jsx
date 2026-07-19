import React, { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";
import Nav from "@/components/Nav";
import { DASH } from "@/constants/testIds";

const STATUS_COLOR = {
  healthy: "text-primary", monitoring: "text-yellow-400",
  diseased: "text-secondary", critical: "text-destructive",
};

export default function FieldsList() {
  const { user } = useAuth();
  const nav = useNavigate();
  const { t } = useTranslation();
  const [fields, setFields] = useState([]);

  useEffect(() => {
    if (!user) { nav("/login"); return; }
    api.get("/fields").then(r => setFields(r.data));
  }, [user, nav]);

  return (
    <div className="min-h-screen">
      <Nav />
      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="mono text-[10px] uppercase tracking-widest text-primary">// inventory</div>
        <h1 className="mt-2 font-heading font-bold text-4xl tracking-tight">{t("nav.fields")}</h1>

        <div className="mt-8 grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {fields.map(f => (
            <Link key={f.id} to={`/fields/${f.id}`} data-testid={DASH.fieldCard}
              className="border border-border bg-card p-5 hover:border-primary/40 transition-colors">
              <div className="mono text-[10px] uppercase tracking-widest text-muted-foreground">{f.region}</div>
              <div className="mt-1 font-heading font-semibold text-lg">{f.name}</div>
              <div className="mt-1 text-xs text-muted-foreground capitalize">{f.crop} · {f.area_hectares} ha</div>
              <div className="mt-4 flex items-baseline gap-2">
                <span className={`font-heading font-bold text-3xl ${STATUS_COLOR[f.status] || "text-foreground"}`}>{Math.round(f.health_score)}</span>
                <span className="text-xs text-muted-foreground uppercase tracking-widest">{t("dash.health")}</span>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
}
