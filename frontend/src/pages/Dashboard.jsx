import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";
import { DASH } from "@/constants/testIds";
import Nav from "@/components/Nav";
import { motion } from "framer-motion";
import { AlertTriangle, Wheat, TrendingUp, Activity, Zap, Upload, Loader2, MapPin } from "lucide-react";
import { LineChart, Line, ResponsiveContainer, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { toast } from "sonner";
import FieldMap from "@/components/FieldMap";

const SEV_COLOR = {
  low: "text-primary border-primary/30",
  moderate: "text-yellow-400 border-yellow-400/30",
  high: "text-secondary border-secondary/30",
  critical: "text-destructive border-destructive/40",
};
const STATUS_COLOR = {
  healthy: "text-primary", monitoring: "text-yellow-400",
  diseased: "text-secondary", critical: "text-destructive",
};

// tiny 1x1 base64 fallback used when the file API is unavailable
const SAMPLE_LEAF_B64 =
  "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAAoACgDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigAooooAKKKKACiiigAooooAKKKKACiiigAooooA//9k=";

export default function Dashboard() {
  const { user, loading: authLoading } = useAuth();
  const nav = useNavigate();
  const { t } = useTranslation();
  const [fields, setFields] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [detections, setDetections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(null); // field_id
  const [showAdd, setShowAdd] = useState(false);

  const load = useCallback(async () => {
    try {
      const [f, a, d] = await Promise.all([
        api.get("/fields"),
        api.get("/alerts?limit=50"),
        api.get("/detections?limit=200"),
      ]);
      setFields(f.data);
      setAlerts(a.data);
      setDetections(d.data);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => {
    if (authLoading) return;
    if (!user) { nav("/login"); return; }
    load();
    const int = setInterval(load, 10000);
    return () => clearInterval(int);
  }, [user, authLoading, nav, load]);

  const scanField = async (field, file) => {
    setScanning(field.id);
    try {
      let image_b64 = SAMPLE_LEAF_B64;
      if (file) {
        image_b64 = await new Promise((res, rej) => {
          const r = new FileReader();
          r.onload = () => res(String(r.result).split(",")[1]);
          r.onerror = rej;
          r.readAsDataURL(file);
        });
      }
      const { data } = await api.post("/inference/enqueue", { field_id: field.id, image_b64 });
      toast.success(`Scan queued for ${field.name}`, { description: `Job ${data.job_id.slice(0, 8)} · polling...` });
      // poll
      const poll = setInterval(async () => {
        const r = await api.get(`/inference/jobs/${data.job_id}`);
        if (r.data.status === "succeeded") {
          clearInterval(poll); setScanning(null);
          toast.success(`Scan complete for ${field.name}`);
          load();
        } else if (r.data.status === "dead") {
          clearInterval(poll); setScanning(null);
          toast.error(`Scan failed: ${r.data.error || "unknown"}`);
        }
      }, 2500);
      setTimeout(() => { clearInterval(poll); setScanning(null); }, 60000);
    } catch (e) {
      setScanning(null);
      toast.error(e.response?.data?.detail || "Failed to enqueue");
    }
  };

  // aggregate trend
  const trend = React.useMemo(() => {
    const byDay = {};
    detections.forEach(d => {
      const day = (d.created_at || "").slice(0, 10);
      if (!day) return;
      if (!byDay[day]) byDay[day] = { day, avg_conf: 0, count: 0, area: 0 };
      byDay[day].avg_conf += d.confidence || 0;
      byDay[day].area += d.affected_area_pct || 0;
      byDay[day].count += 1;
    });
    return Object.values(byDay).map(x => ({
      day: x.day.slice(5),
      health: Math.max(0, 100 - x.area / x.count),
      confidence: (x.avg_conf / x.count) * 100,
    })).sort((a, b) => a.day.localeCompare(b.day));
  }, [detections]);

  const totals = {
    fields: fields.length,
    critical: fields.filter(f => f.status === "critical").length,
    monitoring: fields.filter(f => f.status === "monitoring" || f.status === "diseased").length,
    avgHealth: fields.length ? Math.round(fields.reduce((s, f) => s + (f.health_score || 0), 0) / fields.length) : 0,
  };

  if (loading) return (
    <div className="min-h-screen"><Nav />
      <div className="mx-auto max-w-7xl px-6 py-16"><Loader2 className="w-6 h-6 animate-spin text-primary" /></div>
    </div>
  );

  return (
    <div className="min-h-screen" data-testid={DASH.root}>
      <Nav />
      <div className="mx-auto max-w-7xl px-6 py-10">
        <div className="flex items-end justify-between flex-wrap gap-4">
          <div>
            <p className="mono text-[10px] tracking-[0.3em] uppercase text-primary">// live ops</p>
            <h1 className="mt-2 font-heading font-bold text-4xl tracking-tight">{t("dash.title")}</h1>
            <p className="mt-2 text-muted-foreground">{t("dash.subtitle")}</p>
          </div>
          <button
            onClick={() => setShowAdd(true)}
            className="px-4 py-2 border border-primary/40 text-primary rounded-sm hover:bg-primary/10 transition-colors mono text-xs uppercase tracking-widest"
          >{t("dash.addField")}</button>
        </div>

        {/* Metrics */}
        <div className="mt-8 grid grid-cols-2 md:grid-cols-4 gap-px bg-border/40">
          {[
            { Icon: Wheat, l: "Fields", v: totals.fields, c: "text-primary" },
            { Icon: AlertTriangle, l: "Critical", v: totals.critical, c: "text-destructive" },
            { Icon: Activity, l: "Monitoring", v: totals.monitoring, c: "text-secondary" },
            { Icon: TrendingUp, l: "Avg health", v: `${totals.avgHealth}%`, c: "text-primary" },
          ].map((m, i) => (
            <div key={i} data-testid={DASH.metric} className="bg-card p-5">
              <div className="flex items-center justify-between">
                <span className="mono text-[10px] tracking-widest uppercase text-muted-foreground">{m.l}</span>
                <m.Icon className={`w-4 h-4 ${m.c}`} />
              </div>
              <div className={`mt-3 font-heading font-bold text-3xl ${m.c}`}>{m.v}</div>
            </div>
          ))}
        </div>

        {/* Chart */}
        <div className="mt-8 border border-border bg-card p-6">
          <div className="flex items-center justify-between">
            <div>
              <div className="mono text-[10px] tracking-widest uppercase text-muted-foreground">{t("dash.trend")}</div>
              <div className="mt-1 font-heading text-xl font-semibold">Fleet-wide signal</div>
            </div>
          </div>
          <div className="mt-4 h-56" data-testid={DASH.trendChart}>
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

        {/* Map */}
        <div className="mt-8">
          <div className="flex items-center gap-2 mb-3">
            <MapPin className="w-4 h-4 text-primary" />
            <div className="mono text-[10px] tracking-widest uppercase text-muted-foreground">field map</div>
          </div>
          <FieldMap
            fields={fields}
            onFieldClick={(f) => nav(`/fields/${f.id}`)}
            height={420}
          />
        </div>

        {/* Fields + Alerts split */}
        <div className="mt-8 grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <h2 className="font-heading text-xl font-semibold mb-4">{t("dash.fields")}</h2>
            {fields.length === 0 ? (
              <div className="border border-dashed border-border p-10 text-center text-muted-foreground">{t("dash.empty")}</div>
            ) : (
              <div className="grid sm:grid-cols-2 gap-4">
                {fields.map((f, i) => (
                  <motion.div
                    key={f.id} data-testid={DASH.fieldCard}
                    initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className="border border-border bg-card p-5 hover:border-primary/40 transition-colors"
                  >
                    <div className="flex items-start justify-between">
                      <Link to={`/fields/${f.id}`} className="group">
                        <div className="mono text-[10px] uppercase tracking-widest text-muted-foreground">{f.region}</div>
                        <div className="mt-1 font-heading font-semibold text-lg group-hover:text-primary transition-colors">{f.name}</div>
                        <div className="mt-1 text-xs text-muted-foreground capitalize">{f.crop} · {f.area_hectares} ha</div>
                      </Link>
                      <span data-testid={DASH.severityBadge} className={`mono text-[10px] uppercase tracking-widest px-2 py-1 border rounded-sm ${STATUS_COLOR[f.status] || "text-muted-foreground"} border-current/30`}>
                        {t(`dash.status_${f.status || "healthy"}`)}
                      </span>
                    </div>
                    <div className="mt-4 flex items-baseline gap-2" data-testid={DASH.healthScore}>
                      <span className={`font-heading font-bold text-3xl ${STATUS_COLOR[f.status] || "text-foreground"}`}>{Math.round(f.health_score)}</span>
                      <span className="text-xs text-muted-foreground uppercase tracking-widest">{t("dash.health")}</span>
                    </div>
                    <div className="mt-4 flex gap-2">
                      <label
                        data-testid={DASH.scanButton}
                        className={`flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-2 text-xs mono uppercase tracking-widest border rounded-sm cursor-pointer transition-colors ${
                          scanning === f.id ? "opacity-50 border-border" : "border-primary/40 text-primary hover:bg-primary/10"
                        }`}
                      >
                        {scanning === f.id ? <><Loader2 className="w-3 h-3 animate-spin" /> {t("dash.uploading")}</> : <><Upload className="w-3 h-3" /> {t("dash.scanNow")}</>}
                        <input
                          type="file" accept="image/*"
                          data-testid={DASH.uploadInput}
                          className="hidden"
                          disabled={scanning === f.id}
                          onChange={(e) => scanField(f, e.target.files?.[0])}
                        />
                      </label>
                      <Link
                        to={`/fields/${f.id}`}
                        className="inline-flex items-center justify-center px-3 py-2 text-xs mono uppercase tracking-widest border border-border rounded-sm hover:border-primary/40 hover:text-primary transition-colors"
                      >
                        {t("dash.openField")}
                      </Link>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}
          </div>

          <div>
            <h2 className="font-heading text-xl font-semibold mb-4">{t("dash.alerts")}</h2>
            {alerts.length === 0 ? (
              <div className="border border-dashed border-border p-6 text-center text-muted-foreground text-sm">{t("dash.alertEmpty")}</div>
            ) : (
              <div className="space-y-2 max-h-[600px] overflow-y-auto">
                {alerts.slice(0, 30).map((a, i) => (
                  <motion.div
                    key={a.id} data-testid={DASH.alertItem}
                    initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: Math.min(i * 0.03, 0.4) }}
                    className={`border-l-2 bg-card p-3 text-sm ${SEV_COLOR[a.severity] || "border-border"}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="mono text-[10px] uppercase tracking-widest">{t(`dash.severity_${a.severity}`)}</span>
                      <span className="mono text-[10px] text-muted-foreground">{new Date(a.created_at).toLocaleString()}</span>
                    </div>
                    <div className="mt-2 text-foreground line-clamp-3">{a.message_en}</div>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {showAdd && <AddFieldModal onClose={() => { setShowAdd(false); load(); }} />}
    </div>
  );
}

function AddFieldModal({ onClose }) {
  const [form, setForm] = useState({ name: "", crop: "wheat", region: "Punjab, India",
                                     area_hectares: 2.0, lat: 30.9, lng: 75.85 });
  const [polygon, setPolygon] = useState(null);
  const [saving, setSaving] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setSaving(true);
    try {
      await api.post("/fields", { ...form, area_hectares: parseFloat(form.area_hectares),
                                   lat: parseFloat(form.lat), lng: parseFloat(form.lng),
                                   polygon: polygon || null });
      toast.success("Field added");
      onClose();
    } catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
    finally { setSaving(false); }
  };
  return (
    <div className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50 flex items-center justify-center p-6" onClick={onClose}>
      <form onSubmit={submit} onClick={(e) => e.stopPropagation()}
        className="border border-border bg-card p-8 rounded-sm w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="mono text-[10px] uppercase tracking-widest text-primary">// new field</div>
        <h3 className="mt-2 font-heading text-2xl font-bold tracking-tight">Add field</h3>
        {["name", "crop", "region"].map(k => (
          <div key={k} className="mt-3">
            <label className="mono text-xs uppercase tracking-widest text-muted-foreground">{k}</label>
            <input required value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              className="mt-1 w-full bg-background border border-border rounded-sm px-3 py-2 focus:outline-none focus:border-primary/60" />
          </div>
        ))}
        <div className="mt-3 grid grid-cols-3 gap-2">
          {["area_hectares", "lat", "lng"].map(k => (
            <div key={k}>
              <label className="mono text-[10px] uppercase tracking-widest text-muted-foreground">{k}</label>
              <input required type="number" step="0.001" value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                className="mt-1 w-full bg-background border border-border rounded-sm px-2 py-2 text-sm focus:outline-none focus:border-primary/60" />
            </div>
          ))}
        </div>

        <div className="mt-5">
          <label className="mono text-xs uppercase tracking-widest text-muted-foreground">Draw field boundary (optional)</label>
          <p className="text-xs text-muted-foreground mt-1 mb-2">Use the polygon tool on the top-left of the map. Centroid auto-fills below.</p>
          <FieldMap
            fields={[]}
            center={[parseFloat(form.lat) || 30.9, parseFloat(form.lng) || 75.85]}
            zoom={11}
            draw
            height={280}
            onPolygonDrawn={(ring, c) => {
              setPolygon(ring);
              setForm(f => ({ ...f, lat: c.lat.toFixed(5), lng: c.lng.toFixed(5) }));
              toast.success(`Polygon captured (${ring.length - 1} vertices)`);
            }}
          />
        </div>

        <button type="submit" disabled={saving}
          className="mt-6 w-full py-2.5 bg-primary text-primary-foreground font-semibold rounded-sm hover:bg-primary/90 transition-colors disabled:opacity-50">
          {saving ? "Saving..." : "Add field"}
        </button>
      </form>
    </div>
  );
}
