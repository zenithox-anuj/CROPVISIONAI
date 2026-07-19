import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { Toaster } from "sonner";
import "@/lib/i18n";

import Landing from "@/pages/Landing";
import AuthPage from "@/pages/AuthPage";
import Dashboard from "@/pages/Dashboard";
import FieldsList from "@/pages/FieldsList";
import FieldDetail from "@/pages/FieldDetail";
import AlertsPage from "@/pages/AlertsPage";
import AgronomistQueue from "@/pages/AgronomistQueue";
import AdminPage from "@/pages/AdminPage";
import CoopDashboard from "@/pages/CoopDashboard";

export default function App() {
  return (
    <div className="App min-h-screen">
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<AuthPage mode="login" />} />
            <Route path="/signup" element={<AuthPage mode="signup" />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/fields" element={<FieldsList />} />
            <Route path="/fields/:id" element={<FieldDetail />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/queue" element={<AgronomistQueue />} />
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/coop" element={<CoopDashboard />} />
          </Routes>
          <Toaster theme="dark" position="top-right" richColors />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}
