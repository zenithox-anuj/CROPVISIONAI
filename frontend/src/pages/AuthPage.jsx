import React, { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";
import { AUTH } from "@/constants/testIds";
import { api } from "@/lib/api";
import Nav from "@/components/Nav";
import { motion } from "framer-motion";

export default function AuthPage({ mode = "login" }) {
  const nav = useNavigate();
  const { login, signup } = useAuth();
  const { t } = useTranslation();
  const [isLogin, setIsLogin] = useState(mode === "login");
  const [email, setEmail] = useState("farmer@cropvision.ai");
  const [password, setPassword] = useState("farmer123");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState("farmer");
  const [coopId, setCoopId] = useState("");
  const [coops, setCoops] = useState([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get("/cooperatives").then(r => setCoops(r.data)).catch(() => {});
  }, []);

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setLoading(true);
    try {
      const u = isLogin
        ? await login(email, password)
        : await signup({ email, password, name, phone: phone || null, role,
                         cooperative_id: coopId || null, language: "en" });
      if (u.role === "agronomist") nav("/queue");
      else if (u.role === "admin") nav("/admin");
      else if (u.role === "coop_admin") nav("/coop");
      else nav("/dashboard");
    } catch (e) {
      setErr(e.response?.data?.detail || "Something went wrong");
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen">
      <Nav />
      <div className="mx-auto max-w-7xl px-6 py-16 grid md:grid-cols-2 gap-12 items-center">
        <div className="hidden md:block">
          <p className="mono text-[10px] tracking-[0.3em] uppercase text-primary">// access</p>
          <h1 className="mt-3 font-heading font-bold text-4xl md:text-5xl tracking-tight leading-tight">
            The command center for<br /><span className="text-primary">every acre you protect.</span>
          </h1>
          <p className="mt-4 text-muted-foreground text-lg leading-relaxed">
            Sign in to see live field health, disease alerts, and advisories generated in seconds.
          </p>
          <div className="mt-8 border border-border p-5 rounded-sm bg-card">
            <div className="mono text-xs text-primary tracking-widest">// demo credentials</div>
            <div className="mt-3 space-y-1 text-sm text-muted-foreground">
              <div>farmer@cropvision.ai / farmer123</div>
              <div>agronomist@cropvision.ai / agro123</div>
              <div>admin@cropvision.ai / admin123</div>
            </div>
          </div>
        </div>

        <motion.form
          initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          onSubmit={submit} className="border border-border bg-card p-8 rounded-sm"
        >
          <h2 className="font-heading text-2xl font-bold tracking-tight">
            {isLogin ? t("auth.login") : t("auth.signup")}
          </h2>

          {!isLogin && (
            <>
              <div className="mt-6">
                <label className="mono text-xs uppercase tracking-widest text-muted-foreground">{t("auth.name")}</label>
                <input
                  data-testid={AUTH.nameInput}
                  value={name} onChange={(e) => setName(e.target.value)} required
                  className="mt-2 w-full bg-background border border-border rounded-sm px-3 py-2.5 focus:outline-none focus:border-primary/60 transition-colors"
                />
              </div>
              <div className="mt-4">
                <label className="mono text-xs uppercase tracking-widest text-muted-foreground">{t("auth.role")}</label>
                <select
                  data-testid={AUTH.roleSelect}
                  value={role} onChange={(e) => setRole(e.target.value)}
                  className="mt-2 w-full bg-background border border-border rounded-sm px-3 py-2.5 focus:outline-none focus:border-primary/60 transition-colors"
                >
                  <option value="farmer">{t("auth.farmer")}</option>
                  <option value="agronomist">{t("auth.agronomist")}</option>
                  <option value="coop_admin">{t("auth.coop_admin")}</option>
                </select>
              </div>
              <div className="mt-4">
                <label className="mono text-xs uppercase tracking-widest text-muted-foreground">{t("auth.phone")}</label>
                <input
                  data-testid="auth-phone"
                  value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91..."
                  className="mt-2 w-full bg-background border border-border rounded-sm px-3 py-2.5 focus:outline-none focus:border-primary/60 transition-colors"
                />
              </div>
              {coops.length > 0 && (
                <div className="mt-4">
                  <label className="mono text-xs uppercase tracking-widest text-muted-foreground">{t("auth.cooperative")}</label>
                  <select
                    data-testid="auth-coop"
                    value={coopId} onChange={(e) => setCoopId(e.target.value)}
                    className="mt-2 w-full bg-background border border-border rounded-sm px-3 py-2.5 focus:outline-none focus:border-primary/60 transition-colors"
                  >
                    <option value="">—</option>
                    {coops.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </div>
              )}
            </>
          )}

          <div className="mt-4">
            <label className="mono text-xs uppercase tracking-widest text-muted-foreground">{t("auth.email")}</label>
            <input
              data-testid={AUTH.emailInput} type="email"
              value={email} onChange={(e) => setEmail(e.target.value)} required
              className="mt-2 w-full bg-background border border-border rounded-sm px-3 py-2.5 focus:outline-none focus:border-primary/60 transition-colors"
            />
          </div>
          <div className="mt-4">
            <label className="mono text-xs uppercase tracking-widest text-muted-foreground">{t("auth.password")}</label>
            <input
              data-testid={AUTH.passwordInput} type="password"
              value={password} onChange={(e) => setPassword(e.target.value)} required minLength={6}
              className="mt-2 w-full bg-background border border-border rounded-sm px-3 py-2.5 focus:outline-none focus:border-primary/60 transition-colors"
            />
          </div>

          {err && (
            <div data-testid={AUTH.error} className="mt-4 border border-destructive/40 bg-destructive/10 text-destructive text-sm p-3 rounded-sm">
              {err}
            </div>
          )}

          <button
            data-testid={AUTH.submit} type="submit" disabled={loading}
            className="mt-6 w-full py-3 bg-primary text-primary-foreground font-semibold rounded-sm hover:bg-primary/90 transition-colors disabled:opacity-50"
          >
            {loading ? t("auth.loading") : t("auth.submit")}
          </button>

          <button
            data-testid={AUTH.toggleMode} type="button"
            onClick={() => setIsLogin(!isLogin)}
            className="mt-4 w-full text-center text-sm text-muted-foreground hover:text-primary transition-colors"
          >
            {isLogin ? t("auth.noAccount") : t("auth.haveAccount")}
          </button>
        </motion.form>
      </div>
    </div>
  );
}
