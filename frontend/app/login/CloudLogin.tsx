"use client";

import { useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { SessionProvider, useSession, signIn, signOut } from "next-auth/react";
import { useAuth } from "../../lib/auth";
import { LoginForm } from "./LoginForm";

interface OAuthSession {
  user?: { name?: string | null; email?: string | null; image?: string | null };
  id_token?: string;
  provider?: string;
  expires: string;
}

// Wrapper that provides SessionProvider context (not in global layout since desktop mode skips OAuth)
export default function CloudLoginWrapper() {
  return (
    <SessionProvider>
      <CloudLoginInner />
    </SessionProvider>
  );
}

function CloudLoginInner() {
  const router = useRouter();
  const { user, login, register, loginWithOAuth, isLoading } = useAuth();
  const { data: session, status } = useSession() as { data: OAuthSession | null; status: string };

  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (session?.user && session.id_token && session.provider) {
      setBusy(true);
      loginWithOAuth(session.provider, session.id_token)
        .then(() => {
          signOut({ redirect: false });
          router.push("/evaluation");
        })
        .catch((err: Error) => {
          signOut({ redirect: false });
          setError(err.message);
          setBusy(false);
        });
    }
  }, [session, loginWithOAuth, router]);

  useEffect(() => {
    if (!isLoading && user) {
      router.replace("/evaluation");
    }
  }, [isLoading, user, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!email || !password) {
      setError("Email y contraseña son obligatorios.");
      return;
    }

    if (mode === "register") {
      if (!username) {
        setError("El nombre de usuario es obligatorio.");
        return;
      }
      if (password.length < 8) {
        setError("La contraseña debe tener al menos 8 caracteres.");
        return;
      }
      if (password !== confirmPassword) {
        setError("Las contraseñas no coinciden.");
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
      setError((err as Error).message);
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
      oauthEnabled
      onGoogleSignIn={() => signIn("google")}
      oauthStatus={status}
    />
  );
}
