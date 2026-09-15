"use client";


import { useLanguage } from "@/context/LanguageContext";
import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import dynamic from "next/dynamic";
import { useAuth } from "../../lib/auth";
import { LoginForm } from "./LoginForm";

const CloudLogin = dynamic(() => import("./CloudLogin"), { ssr: false });

export default function LoginPage() {
  const [isDesktop, setIsDesktop] = useState<boolean | null>(null);

  useEffect(() => {
    // Tauri v2 inyecta `window.__TAURI_INTERNALS__` (siempre); `window.__TAURI__`
    // solo con `app.withGlobalTauri: true` (default false). Sin esto, la app
    // de escritorio caía en CloudLogin (flujo web OAuth) en vez de DesktopLogin.
    setIsDesktop("__TAURI_INTERNALS__" in window || "__TAURI__" in window);
  }, []);

  if (isDesktop === null) {
    return (
      <main className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </main>
    );
  }

  if (!isDesktop) {
    return <CloudLogin />;
  }

  return <DesktopLogin />;
}

function DesktopLogin() {
  const { t } = useLanguage();
  const router = useRouter();
  const { user, login, register, isLoading } = useAuth();

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && user) {
      router.replace("/evaluation");
    }
  }, [isLoading, user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email || !password) {
      setError(t("auto_32983b1d7ac2"));
      return;
    }

    if (mode === "register") {
      if (!username) {
        setError(t("auto_4b66d3c2fe33"));
        return;
      }
      if (password.length < 8) {
        setError(t("auto_0af4040d3c39"));
        return;
      }
      if (password !== confirmPassword) {
        setError(t("auto_ebb21b20058c"));
        return;
      }
    }

    setBusy(true);
    try {
      if (mode === "login") {
        await login(email, password);
      } else {
        await register(email, username, password);
      }
      router.push("/evaluation");
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message
          : typeof err === "string"
            ? err
            : "Ocurrió un error inesperado. Intenta de nuevo.";
      setError(msg);
    } finally {
      setBusy(false);
    }
  };

  if (isLoading) {
    return (
      <main className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-brand-500 border-t-transparent" />
      </main>
    );
  }

  if (user) return null;

  return (
    <LoginForm
      mode={mode}
      setMode={setMode}
      email={email}
      setEmail={setEmail}
      username={username}
      setUsername={setUsername}
      password={password}
      setPassword={setPassword}
      confirmPassword={confirmPassword}
      setConfirmPassword={setConfirmPassword}
      busy={busy}
      error={error}
      onSubmit={handleSubmit}
      oauthEnabled={false}
    />
  );
}
