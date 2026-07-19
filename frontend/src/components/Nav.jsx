import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { useTranslation } from "react-i18next";
import { NAV } from "@/constants/testIds";
import { Satellite, LogOut, Languages } from "lucide-react";

export default function Nav() {
  const { user, logout } = useAuth();
  const { t, i18n } = useTranslation();
  const loc = useLocation();
  const nav = useNavigate();

  const toggleLang = () => {
    const next = i18n.language === "en" ? "hi" : "en";
    i18n.changeLanguage(next);
    localStorage.setItem("cv_lang", next);
  };

  const link = (to, label, id) => {
    const active = loc.pathname === to || (to !== "/" && loc.pathname.startsWith(to));
    return (
      <Link
        to={to}
        data-testid={id}
        className={`px-3 py-2 text-sm font-medium tracking-wide transition-colors duration-200 ${
          active ? "text-primary" : "text-muted-foreground hover:text-foreground"
        }`}
      >
        {label}
      </Link>
    );
  };

  return (
    <header className="sticky top-0 z-40 bg-background/70 backdrop-blur-xl backdrop-saturate-150 border-b border-white/5">
      <div className="mx-auto max-w-7xl px-6 h-16 flex items-center justify-between">
        <Link to="/" data-testid={NAV.logo} className="flex items-center gap-2 group">
          <div className="w-8 h-8 rounded-sm bg-primary/10 border border-primary/40 flex items-center justify-center glow-green">
            <Satellite className="w-4 h-4 text-primary" />
          </div>
          <div className="font-heading font-bold text-lg tracking-tight">
            Crop<span className="text-primary">Vision</span><span className="text-muted-foreground text-xs ml-1 mono">AI</span>
          </div>
        </Link>

        <nav className="hidden md:flex items-center gap-1">
          {link("/", t("nav.home"), NAV.home)}
          {user && link("/dashboard", t("nav.dashboard"), NAV.dashboard)}
          {user && link("/fields", t("nav.fields"), NAV.fields)}
          {user && link("/alerts", t("nav.alerts"), NAV.alerts)}
          {user?.role === "agronomist" && link("/queue", t("nav.agronomist"), NAV.agronomist)}
          {user?.role === "coop_admin" && link("/coop", t("nav.coop"), NAV.coop)}
          {user?.role === "admin" && link("/coop", t("nav.coop"), NAV.coop)}
          {user?.role === "admin" && link("/admin", t("nav.admin"), NAV.admin)}
        </nav>

        <div className="flex items-center gap-2">
          <button
            data-testid={NAV.langToggle}
            onClick={toggleLang}
            className="flex items-center gap-1 px-3 py-1.5 rounded-sm border border-border/60 text-xs mono uppercase tracking-widest text-muted-foreground hover:text-primary hover:border-primary/40 transition-colors"
          >
            <Languages className="w-3 h-3" />
            {i18n.language}
          </button>
          {user ? (
            <button
              data-testid={NAV.logout}
              onClick={() => { logout(); nav("/"); }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-sm rounded-sm border border-border/60 hover:border-destructive/60 hover:text-destructive transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" /> {t("nav.logout")}
            </button>
          ) : (
            <>
              <Link to="/login" data-testid={NAV.login} className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors">
                {t("nav.login")}
              </Link>
              <Link to="/signup" data-testid={NAV.signup} className="px-4 py-1.5 text-sm bg-primary text-primary-foreground rounded-sm font-semibold hover:bg-primary/90 transition-colors">
                {t("nav.signup")}
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
