"use client";

import { useLanguage } from "../../context/LanguageContext";

interface LoginFormProps {
  mode: "login" | "register";
  setMode: (m: "login" | "register") => void;
  email: string;
  setEmail: (v: string) => void;
  username: string;
  setUsername: (v: string) => void;
  password: string;
  setPassword: (v: string) => void;
  confirmPassword: string;
  setConfirmPassword: (v: string) => void;
  busy: boolean;
  error: string | null;
  onSubmit: (e: React.FormEvent) => void;
  oauthEnabled: boolean;
  onGoogleSignIn?: () => void;
  oauthStatus?: string;
}

export function LoginForm({
  mode, setMode, email, setEmail, username, setUsername,
  password, setPassword, confirmPassword, setConfirmPassword,
  busy, error, onSubmit, oauthEnabled, onGoogleSignIn, oauthStatus,
}: LoginFormProps) {
  const { t, locale } = useLanguage();

  const getTitle = () => {
    if (mode === "login") return t("login_title");
    const dict: Record<string, string> = {
      es: "Crear cuenta MolDesign",
      en: "Create MolDesign Account",
      pt: "Criar conta MolDesign",
      fr: "Créer un compte MolDesign",
      de: "MolDesign-Konto erstellen",
      it: "Crea account MolDesign",
      zh: "创建 MolDesign 账号",
      ja: "MolDesign アカウント作成",
      ko: "MolDesign 계정 생성",
      ru: "Создать аккаунт MolDesign",
      hi: "MolDesign खाता बनाएँ",
      ar: "إنشاء حساب MolDesign",
      tr: "MolDesign Hesabı Oluştur",
    };
    return dict[locale] || dict.es;
  };

  const getSubtitle = () => {
    if (mode === "login") return t("login_subtitle");
    const dict: Record<string, string> = {
      es: "Regístrate para acceder al pipeline científico local",
      en: "Register to access the local scientific pipeline",
      pt: "Registre-se para acessar o pipeline científico local",
      fr: "Inscrivez-vous pour accéder au pipeline scientifique local",
      de: "Registrieren Sie sich, um auf die lokale wissenschaftliche Pipeline zuzugreifen",
      it: "Registrati per accedere alla pipeline scientifica locale",
      zh: "注册以访问本地科学计算流程",
      ja: "ローカル科学パイプラインにアクセスするために登録する",
      ko: "로컬 과학 파이프라인에 액세스하려면 등록하십시오",
      ru: "Зарегистрируйтесь для доступа к локальному научному конвейеру",
      hi: "स्थानीय वैज्ञानिक पाइपलाइन तक पहुँचने के लिए पंजीकरण करें",
      ar: "سجل للوصول إلى خط الأنابيب العلمي المحلي",
      tr: "Yerel bilimsel işlem hattına erişmek için kaydolun",
    };
    return dict[locale] || dict.es;
  };

  const getRegisterText = () => {
    const dict: Record<string, string> = {
      es: "Registrarse",
      en: "Register",
      pt: "Registrar-se",
      fr: "S'inscrire",
      de: "Registrieren",
      it: "Registrati",
      zh: "注册",
      ja: "登録",
      ko: "등록",
      ru: "Регистрация",
      hi: "पंजीकरण",
      ar: "تسجيل",
      tr: "Kaydol",
    };
    return dict[locale] || dict.es;
  };

  const getConfirmPasswordText = () => {
    const dict: Record<string, string> = {
      es: "Confirmar Contraseña",
      en: "Confirm Password",
      pt: "Confirmar Senha",
      fr: "Confirmer le mot de passe",
      de: "Passwort bestätigen",
      it: "Conferma Password",
      zh: "确认密码",
      ja: "パスワードの確認",
      ko: "비밀번호 확인",
      ru: "Подтвердите пароль",
      hi: "पासवर्ड की पुष्टि करें",
      ar: "تأكيد كلمة المرور",
      tr: "Şifreyi Onayla",
    };
    return dict[locale] || dict.es;
  };

  const getWarningText = () => {
    const dict: Record<string, string> = {
      es: "MolDesign es una herramienta de investigación computacional. Los resultados no constituyen evidencia clínica.",
      en: "MolDesign is a computational research tool. Results do not constitute clinical evidence.",
      pt: "MolDesign é uma ferramenta de pesquisa computacional. Os resultados não constituem evidência clínica.",
      fr: "MolDesign est un outil de recherche computationnelle. Les résultats ne constituent pas une preuve clinique.",
      de: "MolDesign ist ein computergestütztes Forschungswerkzeug. Die Ergebnisse stellen keine klinische Evidenz dar.",
      it: "MolDesign è uno strumento di ricerca computazionale. I risultati no costituiscono evidenza clinica.",
      zh: "MolDesign 是一个计算研究工具。评估结果不构成临床证据。",
      ja: "MolDesignは計算科学研究ツールです。結果は臨床的なエビデンスを構成するものではありません。",
      ko: "MolDesign은 계산 연구 도구입니다. 결과는 임상적 증거를 구성하지 않습니다.",
      ru: "MolDesign — это инструмент компьютерных исследований. Результаты не являются клиническим доказательством.",
      hi: "MolDesign एक कम्प्यूटेशनल अनुसंधान उपकरण है। परिणाम नैदानिक साक्ष्य नहीं हैं।",
      ar: "MolDesign هو أداة بحث حاسوبية. النتائج لا تشكل دليلاً سريرياً.",
      tr: "MolDesign hesaplamalı bir araştırma aracıdır. Sonuçlar klinik kanıt oluşturmaz.",
    };
    return dict[locale] || dict.es;
  };

  return (
    <main className="flex min-h-[calc(100vh-8rem)] items-center justify-center">
      <div className="w-full max-w-md space-y-6 rounded-2xl border border-surface-700 bg-surface-900/50 p-8 shadow-2xl backdrop-blur-md">
        <div className="space-y-2 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100 uppercase font-mono">
            {getTitle()}
          </h1>
          <p className="text-sm text-surface-400">
            {getSubtitle()}
          </p>
        </div>

        {/* Badge cuenta local */}
        <div className="flex items-center justify-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/5 px-4 py-2.5 text-xs text-emerald-400 font-medium">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse shrink-0" />
          {t("login_privacy_badge")}
        </div>

        {error && (
          <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-400 font-mono">
            {error}
          </div>
        )}

        <div className="flex rounded-xl bg-surface-800 p-1">
          <button
            type="button"
            onClick={() => { setMode("login"); }}
            className={`w-1/2 rounded-lg py-2 text-sm font-medium transition-all font-mono uppercase tracking-wider ${
              mode === "login"
                ? "bg-surface-700 text-white shadow"
                : "text-surface-400 hover:text-white"
            }`}
          >
            {t("login")}
          </button>
          <button
            type="button"
            onClick={() => { setMode("register"); }}
            className={`w-1/2 rounded-lg py-2 text-sm font-medium transition-all font-mono uppercase tracking-wider ${
              mode === "register"
                ? "bg-brand-600 text-white shadow"
                : "text-surface-400 hover:text-white"
            }`}
          >
            {getRegisterText()}
          </button>
        </div>

        <form onSubmit={onSubmit} className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="login-email" className="text-sm font-medium text-surface-300 font-mono">Email</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-xl border border-surface-700 bg-surface-800 px-4 py-3 text-sm text-zinc-900 dark:text-zinc-100 placeholder-surface-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
              placeholder="tu@email.com"
            />
          </div>

          {mode === "register" && (
            <div className="space-y-2">
              <label htmlFor="login-username" className="text-sm font-medium text-surface-300 font-mono">{t("login_username")}</label>
              <input
                id="login-username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full rounded-xl border border-surface-700 bg-surface-800 px-4 py-3 text-sm text-zinc-900 dark:text-zinc-100 placeholder-surface-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
                placeholder="usuario123"
              />
            </div>
          )}

          <div className="space-y-2">
            <label htmlFor="login-password" className="text-sm font-medium text-surface-300 font-mono">{t("login_password")}</label>
            <input
              id="login-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-surface-700 bg-surface-800 px-4 py-3 text-sm text-zinc-900 dark:text-zinc-100 placeholder-surface-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
              placeholder="••••••••"
            />
          </div>

          {mode === "register" && (
            <div className="space-y-2">
              <label htmlFor="login-confirm" className="text-sm font-medium text-surface-300 font-mono">{getConfirmPasswordText()}</label>
              <input
                id="login-confirm"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="w-full rounded-xl border border-surface-700 bg-surface-800 px-4 py-3 text-sm text-zinc-900 dark:text-zinc-100 placeholder-surface-500 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 font-mono"
                placeholder="••••••••"
              />
            </div>
          )}

          <button
            type="submit"
            disabled={busy || oauthStatus === "loading"}
            className="w-full rounded-xl bg-brand-600 py-3 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-50 font-mono uppercase tracking-wider"
          >
            {busy || oauthStatus === "loading" ? (
              <span className="flex items-center justify-center gap-2">
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                {mode === "login" ? "..." : "..."}
              </span>
            ) : mode === "login" ? (
              t("login_btn")
            ) : (
              getRegisterText()
            )}
          </button>
        </form>

        {oauthEnabled && (
          <>
            <div className="relative flex items-center py-2">
              <div className="flex-grow border-t border-surface-700"></div>
              <span className="mx-4 flex-shrink-0 text-xs text-surface-500 uppercase tracking-widest font-mono">
                {locale === "es" ? t("auto_519ddde05991") : t("auto_519ddde05991")}
              </span>
              <div className="flex-grow border-t border-surface-700"></div>
            </div>
            <div className="flex flex-col gap-3">
              <button
                type="button"
                disabled={busy || oauthStatus === "loading"}
                className="flex w-full items-center justify-center gap-3 rounded-xl border border-surface-700 bg-surface-800 py-3 text-sm font-medium text-white transition-all hover:bg-surface-700 hover:border-surface-600 disabled:opacity-50"
                onClick={onGoogleSignIn}
              >
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <path d="M22.56 12.25C22.56 11.47 22.49 10.72 22.36 10H12V14.26H17.92C17.66 15.63 16.88 16.8 15.71 17.58V20.34H19.28C21.36 18.42 22.56 15.6 22.56 12.25Z" fill="#4285F4"/>
                  <path d="M12 23C14.97 23 17.46 22.02 19.28 20.34L15.71 17.58C14.72 18.24 13.46 18.66 12 18.66C9.17 18.66 6.77 16.75 5.88 14.19H2.18V17.06C4.01 20.69 7.73 23 12 23Z" fill="#34A853"/>
                  <path d="M5.88 14.19C5.65 13.52 5.52 12.78 5.52 12C5.52 11.22 5.65 10.48 5.88 9.81V6.94H2.18C1.43 8.44 1 10.16 1 12C1 13.84 1.43 15.56 2.18 17.06L5.88 14.19Z" fill="#FBBC05"/>
                  <path d="M12 5.34C13.62 5.34 15.06 5.89 16.2 6.98L19.35 3.83C17.45 2.06 14.97 1 12 1C7.73 1 4.01 3.31 2.18 6.94L5.88 9.81C6.77 7.25 9.17 5.34 12 5.34Z" fill="#EA4335"/>
                </svg>
                Google
              </button>
            </div>
          </>
        )}

        <p className="text-center text-[10px] text-surface-500 font-mono tracking-wide leading-normal">
          {getWarningText()}
        </p>
      </div>
    </main>
  );
}
