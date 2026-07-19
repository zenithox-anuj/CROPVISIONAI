import React from "react";
import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { useTranslation } from "react-i18next";
import { LANDING } from "@/constants/testIds";
import { ArrowRight, Satellite, Brain, Workflow, Sprout, Activity, Zap } from "lucide-react";
import Nav from "@/components/Nav";

const HERO_IMG = "https://images.unsplash.com/photo-1781816928201-ff564c99528a?crop=entropy&cs=srgb&fm=jpg&q=85&w=2000";
const STORY_IMG = "https://images.unsplash.com/photo-1761839257870-06874bda71b5?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600";
const DRONE_IMG = "https://images.unsplash.com/photo-1781816928287-e71d9a6c548c?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600";

export default function Landing() {
  const { t } = useTranslation();

  return (
    <div className="min-h-screen relative">
      <Nav />

      {/* HERO */}
      <section data-testid={LANDING.hero} className="relative overflow-hidden" style={{ minHeight: "88vh" }}>
        <div className="absolute inset-0 z-0">
          <img src={HERO_IMG} alt="Satellite" className="w-full h-full object-cover opacity-40" />
          <div className="absolute inset-0 bg-gradient-to-b from-background/60 via-background/40 to-background" />
          <div className="absolute inset-0 grain" />
        </div>

        <div className="relative z-10 mx-auto max-w-7xl px-6 pt-24 pb-32">
          <motion.div
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
            className="inline-flex items-center gap-2 px-3 py-1.5 rounded-sm border border-primary/30 bg-primary/5 mono text-[10px] tracking-[0.3em] uppercase text-primary"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulseGlow" />
            {t("landing.eyebrow")}
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.1 }}
            className="mt-6 font-heading font-bold text-5xl sm:text-6xl lg:text-7xl leading-[0.95] tracking-tight max-w-4xl"
          >
            {t("landing.heroTitle").split(".").map((s, i, arr) => (
              <span key={i} className={i === arr.length - 2 ? "text-primary text-glow-green" : ""}>
                {s}{i < arr.length - 1 && "."}
              </span>
            ))}
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="mt-6 max-w-2xl text-lg text-muted-foreground leading-relaxed"
          >
            {t("landing.heroSub")}
          </motion.p>

          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}
            transition={{ duration: 0.8, delay: 0.35 }}
            className="mt-10 flex flex-wrap items-center gap-4"
          >
            <Link
              to="/dashboard" data-testid={LANDING.ctaPrimary}
              className="group inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground font-semibold rounded-sm hover:bg-primary/90 transition-colors glow-green"
            >
              {t("landing.cta")}
              <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
            </Link>
            <a href="#how" data-testid={LANDING.ctaSecondary}
              className="inline-flex items-center gap-2 px-6 py-3 border border-border rounded-sm hover:border-primary/40 hover:text-primary transition-colors">
              {t("landing.cta2")}
            </a>
          </motion.div>

          {/* satellite scan strip */}
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }}
            className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-px bg-border/40 max-w-4xl"
          >
            {[
              { k: "12,847", l: t("landing.m1") },
              { k: "< 90s", l: t("landing.m2") },
              { k: "8", l: t("landing.m3") },
              { k: "99.94%", l: t("landing.m4") },
            ].map((m, i) => (
              <div key={i} data-testid={LANDING.metricCard} className="bg-background/80 p-5">
                <div className="font-heading font-bold text-2xl text-primary mono">{m.k}</div>
                <div className="mt-1 text-xs text-muted-foreground uppercase tracking-widest">{m.l}</div>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* FEATURES */}
      <section className="relative py-24 border-t border-border/50">
        <div className="mx-auto max-w-7xl px-6">
          <div className="max-w-2xl">
            <p className="mono text-[10px] tracking-[0.3em] uppercase text-primary">// pipeline</p>
            <h2 className="mt-3 font-heading font-bold text-4xl md:text-5xl tracking-tight">{t("landing.featuresTitle")}</h2>
            <p className="mt-4 text-muted-foreground text-lg">{t("landing.featuresSub")}</p>
          </div>

          <div className="mt-16 grid md:grid-cols-2 gap-px bg-border/40">
            {[
              { Icon: Satellite, t: t("landing.f1t"), d: t("landing.f1d"), c: "text-primary" },
              { Icon: Brain, t: t("landing.f2t"), d: t("landing.f2d"), c: "text-secondary" },
              { Icon: Workflow, t: t("landing.f3t"), d: t("landing.f3d"), c: "text-primary" },
              { Icon: Sprout, t: t("landing.f4t"), d: t("landing.f4d"), c: "text-secondary" },
            ].map((f, i) => (
              <motion.div
                key={i} data-testid={LANDING.featureCard}
                initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }} transition={{ duration: 0.5, delay: i * 0.08 }}
                className="bg-card p-8 md:p-12 group"
              >
                <div className={`w-12 h-12 border border-border flex items-center justify-center mb-6 ${f.c}`}>
                  <f.Icon className="w-6 h-6" />
                </div>
                <h3 className="font-heading text-2xl font-semibold tracking-tight">{f.t}</h3>
                <p className="mt-3 text-muted-foreground leading-relaxed">{f.d}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* HOW */}
      <section id="how" className="relative py-24 border-t border-border/50 overflow-hidden">
        <div className="absolute inset-0 opacity-20 z-0">
          <img src={DRONE_IMG} alt="" className="w-full h-full object-cover" />
          <div className="absolute inset-0 bg-background/70" />
        </div>
        <div className="relative z-10 mx-auto max-w-7xl px-6">
          <p className="mono text-[10px] tracking-[0.3em] uppercase text-primary">// flow</p>
          <h2 className="mt-3 font-heading font-bold text-4xl md:text-5xl tracking-tight">{t("landing.howTitle")}</h2>

          <div className="mt-16 grid md:grid-cols-4 gap-px bg-border/40">
            {[
              { n: "01", l: t("landing.how1"), Icon: Satellite },
              { n: "02", l: t("landing.how2"), Icon: Zap },
              { n: "03", l: t("landing.how3"), Icon: Brain },
              { n: "04", l: t("landing.how4"), Icon: Activity },
            ].map((s, i) => (
              <div key={i} className="bg-card p-8 relative">
                <div className="mono text-xs text-primary tracking-widest">{s.n}</div>
                <s.Icon className="mt-4 w-6 h-6 text-primary" />
                <div className="mt-4 font-heading font-semibold text-lg">{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* STORYTELLING */}
      <section className="py-24 border-t border-border/50">
        <div className="mx-auto max-w-7xl px-6 grid md:grid-cols-2 gap-12 items-center">
          <div className="relative">
            <img src={STORY_IMG} alt="Farmer" className="w-full aspect-[4/5] object-cover rounded-sm" />
            <div className="absolute -bottom-4 -right-4 border border-primary/40 bg-background p-4 rounded-sm mono text-xs glow-green">
              <div className="text-primary">DETECTION</div>
              <div className="mt-1">Leaf Rust · High severity</div>
              <div className="text-muted-foreground mt-1">confidence 0.89 · 34% affected</div>
            </div>
          </div>
          <div>
            <p className="mono text-[10px] tracking-[0.3em] uppercase text-secondary">// last mile</p>
            <h3 className="mt-3 font-heading font-bold text-3xl md:text-4xl tracking-tight leading-tight">
              A farmer doesn't need a dashboard.<br />
              <span className="text-primary">They need the right message, on time, in their language.</span>
            </h3>
            <p className="mt-4 text-muted-foreground leading-relaxed">
              CropVision AI writes advisories in the farmer's language, delivers them over WhatsApp or SMS,
              and escalates to a human agronomist the moment confidence drops.
              No model is perfect — the pipeline is.
            </p>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 border-t border-border/50">
        <div className="mx-auto max-w-4xl px-6">
          <div className="border border-primary/30 bg-primary/5 p-10 md:p-16 relative overflow-hidden">
            <div className="absolute -top-20 -right-20 w-64 h-64 rounded-full bg-primary/10 blur-3xl" />
            <p className="mono text-[10px] tracking-[0.3em] uppercase text-primary relative z-10">// start</p>
            <h3 className="mt-3 font-heading font-bold text-3xl md:text-5xl tracking-tight relative z-10">
              {t("landing.ctaFinal")}
            </h3>
            <p className="mt-4 text-muted-foreground text-lg relative z-10">{t("landing.ctaFinalSub")}</p>
            <div className="mt-8 flex gap-4 relative z-10">
              <Link to="/dashboard" className="inline-flex items-center gap-2 px-6 py-3 bg-primary text-primary-foreground font-semibold rounded-sm hover:bg-primary/90 transition-colors">
                {t("landing.cta")} <ArrowRight className="w-4 h-4" />
              </Link>
              <Link to="/login" className="inline-flex items-center gap-2 px-6 py-3 border border-border rounded-sm hover:border-primary/40 transition-colors">
                {t("nav.login")}
              </Link>
            </div>
          </div>
        </div>
      </section>

      <footer className="border-t border-border/50 py-10">
        <div className="mx-auto max-w-7xl px-6 flex flex-wrap gap-4 justify-between items-center text-sm text-muted-foreground">
          <div>© 2026 CropVision AI · Built for the field</div>
          <div className="mono text-xs">v1.0.0 · claude-sonnet-4.5 · langgraph · n8n</div>
        </div>
      </footer>
    </div>
  );
}
