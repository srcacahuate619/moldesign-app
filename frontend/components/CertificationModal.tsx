/* Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V4 */
/* Hallmark · component: modal · genre: modern-minimal · theme: MolDesign existing
 * states: default · hover · focus · active · disabled · loading · error · success
 * contrast: pass
 */
"use client";

import React, { useEffect, useId, useRef, useState } from "react";
import { useLanguage } from "../context/LanguageContext";
import { urlDelExplorador } from "../lib/moldex";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  ExternalLink as IconoEnlaceExterno,
  KeyRound,
  FlaskConical,
  ShieldCheck,
  Wallet,
  X,
} from "lucide-react";
import { useConnection, useWallet } from "@solana/wallet-adapter-react";
import { WalletMultiButton } from "@solana/wallet-adapter-react-ui";
import { Keypair, LAMPORTS_PER_SOL, PublicKey, sendAndConfirmTransaction, Transaction, TransactionInstruction } from "@solana/web3.js";

import {
  checkBlockchainHealth,
  linkCertification,
  prepareCertification,
} from "../lib/api";
import { isDesktopRuntime } from "../lib/tauri";
import { ThinkingOrb } from "./ui/ThinkingOrb";

import { ExternalLink } from "@/components/ui/ExternalLink";
const MEMO_PROGRAM_ID = new PublicKey("MemoSq4gqABAXKb96qnH8TysNcWxMyWCqXgDLGmfcHr");
const SOLANA_WALLETS_URL = "https://solana.com/wallets";

export interface CertificationSuccess {
  signature: string;
  signer: "experimental" | "wallet";
}

interface CertificationModalProps {
  moleculeId: string;
  onClose: () => void;
  onSuccess: (result: CertificationSuccess) => void;
}

type FlowStep =
  | "select"
  | "poc-confirm"
  | "poc-funding"
  | "poc-signing"
  | "wallet"
  | "web3-prepare"
  | "web3-signing"
  | "verifying"
  | "create-wallet"
  | "done"
  | "error";

const PROCESSING_STEPS = new Set<FlowStep>([
  "poc-funding",
  "poc-signing",
  "web3-prepare",
  "web3-signing",
  "verifying",
]);

function ChoiceIcon({ children }: { children: React.ReactNode }) {
  return (
    <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-white/10 bg-white/[0.03] text-white/60">
      {children}
    </span>
  );
}

export function CertificationModal({ moleculeId, onClose, onSuccess }: CertificationModalProps) {
  const { t } = useLanguage();
  const { publicKey, sendTransaction } = useWallet();
  const { connection } = useConnection();
  const billeteraNoDisponible = isDesktopRuntime();
  const titleId = useId();
  const primaryChoiceRef = useRef<HTMLButtonElement>(null);

  const [step, setStep] = useState<FlowStep>("select");
  const [error, setError] = useState<string | null>(null);
  const [receipt, setReceipt] = useState<CertificationSuccess | null>(null);
  const [health, setHealth] = useState<{
    available: boolean;
    network: string;
    signer?: string;
    reason?: string | null;
  } | null>(null);

  const isProcessing = PROCESSING_STEPS.has(step);

  useEffect(() => {
    let active = true;
    void checkBlockchainHealth().then((result) => {
      if (active) setHealth(result);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    primaryChoiceRef.current?.focus();
  }, []);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !isProcessing) onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isProcessing, onClose]);

  const complete = (result: CertificationSuccess) => {
    setReceipt(result);
    setStep("done");
    onSuccess(result);
  };

  const handleDevnetPoc = async () => {
    if (!health?.available) {
      setError(health?.reason || t("ce_devnet_no_disponible"));
      return;
    }
    setStep("poc-funding");
    setError(null);
    try {
      // Identity is intentionally ephemeral: it exists only for this devnet
      // proof. No secret is persisted or sent to the backend.
      const ephemeralSigner = Keypair.generate();
      const prepared = await prepareCertification(moleculeId, ephemeralSigner.publicKey.toBase58());

      if (prepared.already_certified && prepared.signature) {
        complete({ signature: prepared.signature, signer: "experimental" });
        return;
      }
      if (!prepared.memo) throw new Error(t("ce_memo_fallido"));

      const fundingSignature = await connection.requestAirdrop(
        ephemeralSigner.publicKey,
        0.01 * LAMPORTS_PER_SOL,
      );
      await connection.confirmTransaction(fundingSignature, "confirmed");

      setStep("poc-signing");
      const transaction = new Transaction().add(
        new TransactionInstruction({
          keys: [],
          programId: MEMO_PROGRAM_ID,
          data: Buffer.from(prepared.memo, "utf-8"),
        }),
      );
      const signature = await sendAndConfirmTransaction(
        connection,
        transaction,
        [ephemeralSigner],
        { commitment: "confirmed" },
      );

      setStep("verifying");
      await linkCertification(moleculeId, signature);
      complete({ signature, signer: "experimental" });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : t("ce_prueba_fallida"),
      );
      setStep("error");
    }
  };

  const handleWeb3 = async () => {
    if (!publicKey) {
      setError(t("ce_conecta_wallet"));
      return;
    }

    setStep("web3-prepare");
    setError(null);
    try {
      const prepared = await prepareCertification(moleculeId, publicKey.toBase58());

      if (prepared.already_certified && prepared.signature) {
        setStep("verifying");
        await linkCertification(moleculeId, prepared.signature);
        complete({ signature: prepared.signature, signer: "wallet" });
        return;
      }

      if (!prepared.memo) throw new Error(t("ce_memo_fallido"));

      setStep("web3-signing");
      const transaction = new Transaction().add(
        new TransactionInstruction({
          keys: [],
          programId: MEMO_PROGRAM_ID,
          data: Buffer.from(prepared.memo, "utf-8"),
        }),
      );
      const signature = await sendTransaction(transaction, connection);

      setStep("verifying");
      await connection.confirmTransaction(signature, "confirmed");
      await linkCertification(moleculeId, signature);
      complete({ signature, signer: "wallet" });
    } catch (err) {
      setError(err instanceof Error ? err.message : t("ce_error_firma"));
      setStep("error");
    }
  };

  const flowLabel = () => {
    switch (step) {
      case "poc-funding":
        return t("ce_paso_faucet");
      case "poc-signing":
        return t("ce_paso_memo");
      case "web3-prepare":
        return t("ce_paso_comprobante");
      case "web3-signing":
        return t("ce_paso_aprobacion");
      case "verifying":
        return t("ce_paso_confirmando");
      default:
        return "Procesando";
    }
  };

  const goBack = () => {
    setError(null);
    setStep("select");
  };

  return (
    <div
      className="fixed inset-0 z-[150] flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !isProcessing) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="flex max-h-[calc(100vh-2rem)] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-white/10 bg-surface-900 shadow-2xl"
      >
        <header className="flex items-start justify-between gap-4 border-b border-white/5 px-5 py-4 sm:px-6">
          <div className="flex min-w-0 items-start gap-3">
            <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-brand-500/30 bg-brand-500/10 text-brand-400">
              <ShieldCheck size={20} />
            </span>
            <div className="min-w-0">
              <h2 id={titleId} className="text-base font-bold text-white sm:text-lg">
                Registrar evidencia en Solana
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-surface-400">
                {t("ce_poc_resumen")}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2 font-mono text-[10px] uppercase tracking-wider">
                <span className="text-surface-400">{health?.network || "comprobando red"}</span>
                <span aria-hidden="true" className="text-surface-700">·</span>
                <span className={health?.available ? "text-emerald-400" : health ? "text-red-400" : "text-surface-400"}>
                  {health?.available ? t("ce_devnet_accesible") : health ? t("ce_devnet_etiqueta") : t("ce_verificando")}
                </span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            aria-label={t("c_cerrar")}
            className="grid h-11 w-11 shrink-0 place-items-center rounded-lg text-surface-400 transition-colors hover:bg-white/5 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 active:bg-white/10 disabled:cursor-not-allowed disabled:opacity-30"
          >
            <X size={18} />
          </button>
        </header>

        <div className="overflow-y-auto p-5 sm:p-6">
          {step === "select" && (
            <div className="space-y-3">
              <div className="mb-5 rounded-lg border border-cyan-500/20 bg-cyan-500/[0.05] p-3 text-xs leading-relaxed text-cyan-100/75">
                {t("ce_poc_experimental")}
              </div>

              <button
                ref={primaryChoiceRef}
                type="button"
                onClick={() => setStep("poc-confirm")}
                className="group flex w-full items-start gap-4 rounded-lg border border-brand-500/30 bg-brand-500/[0.08] p-4 text-left transition-colors hover:border-brand-400/60 hover:bg-brand-500/[0.12] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 active:bg-brand-500/[0.16]"
              >
                <ChoiceIcon><FlaskConical size={19} /></ChoiceIcon>
                <span className="min-w-0 flex-1">
                  <span className="flex flex-wrap items-center gap-2 font-bold text-white">
                    Ejecutar prueba devnet
                    <span className="rounded border border-brand-500/30 bg-brand-500/10 px-2 py-0.5 font-mono text-[9px] uppercase tracking-wider text-brand-400">
                      Experimental
                    </span>
                  </span>
                  <span className="mt-1 block text-xs leading-relaxed text-surface-400">
                    {t("ce_efimera_detalle")}
                  </span>
                </span>
              </button>

              <button
                type="button"
                onClick={() => setStep("wallet")}
                disabled={billeteraNoDisponible}
                title={billeteraNoDisponible ? t("ce_wallets_solo_web") : undefined}
                className="group flex w-full items-start gap-4 rounded-lg border border-white/10 bg-white/[0.02] p-4 text-left transition-colors hover:border-white/20 hover:bg-white/[0.04] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 active:bg-white/[0.06]"
              >
                <ChoiceIcon><Wallet size={19} /></ChoiceIcon>
                <span className="min-w-0 flex-1">
                  <span className="font-bold text-white">{t("ce_tengo_wallet")}</span>
                  <span className="mt-1 block text-xs leading-relaxed text-surface-400">
                    {t("ce_wallet_detalle")}
                  </span>
                </span>
              </button>
              {billeteraNoDisponible && (
                <p className="px-2 text-[10px] font-semibold uppercase tracking-wide text-amber-300/80">{t("ce_solo_navegador")}</p>
              )}

              <button
                type="button"
                onClick={() => setStep("create-wallet")}
                className="group flex w-full items-start gap-4 rounded-lg border border-white/10 bg-white/[0.02] p-4 text-left transition-colors hover:border-white/20 hover:bg-white/[0.04] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 active:bg-white/[0.06]"
              >
                <ChoiceIcon><KeyRound size={19} /></ChoiceIcon>
                <span className="min-w-0 flex-1">
                  <span className="font-bold text-white">{t("ce_quiero_wallet")}</span>
                  <span className="mt-1 block text-xs leading-relaxed text-surface-400">
                    {t("ce_directorio_detalle")}
                  </span>
                </span>
              </button>
            </div>
          )}

          {step === "poc-confirm" && (
            <div className="space-y-5">
              <button type="button" onClick={goBack} className="flex min-h-11 items-center gap-2 text-xs font-bold text-surface-400 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400">
                <ArrowLeft size={15} /> {t("ce_cambiar_metodo")}
              </button>
              <div>
                <h3 className="text-base font-bold text-white">{t("ce_prueba_tecnica")}</h3>
                <p className="mt-2 text-sm leading-relaxed text-surface-400">
                  {t("ce_red_pruebas")}
                </p>
              </div>
              <dl className="divide-y divide-white/5 rounded-lg border border-white/10 bg-black/20 px-4">
                <div className="flex items-center justify-between gap-4 py-3 text-xs"><dt className="text-surface-400">Fondos</dt><dd className="font-bold text-white">{t("ce_faucet_sin_valor")}</dd></div>
                <div className="flex items-center justify-between gap-4 py-3 text-xs"><dt className="text-surface-400">Firma</dt><dd className="font-bold text-white">{t("ce_identidad_efimera")}</dd></div>
                <div className="flex items-center justify-between gap-4 py-3 text-xs"><dt className="text-surface-400">Red</dt><dd className="font-mono text-white">{health?.network || "—"}</dd></div>
                <div className="flex items-center justify-between gap-4 py-3 text-xs"><dt className="text-surface-400">{t("ce_datos_cientificos")}</dt><dd className="font-bold text-white">Permanecen locales</dd></div>
              </dl>
              {health && !health.available && (
                <div role="alert" className="flex gap-2 rounded-lg border border-red-500/25 bg-red-500/[0.07] p-3 text-xs leading-relaxed text-red-300">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  {health.reason || t("ce_devnet_no_disponible_corto")}
                </div>
              )}
              <button
                type="button"
                onClick={() => void handleDevnetPoc()}
                disabled={!health?.available}
                className="flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 text-xs font-bold uppercase tracking-wider text-white transition-colors hover:bg-brand-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white active:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <FlaskConical size={16} /> Ejecutar POC
              </button>
            </div>
          )}

          {step === "wallet" && (
            <div className="space-y-5">
              <button type="button" onClick={goBack} className="flex min-h-11 items-center gap-2 text-xs font-bold text-surface-400 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400">
                <ArrowLeft size={15} /> {t("ce_cambiar_metodo")}
              </button>
              <div>
                <h3 className="text-base font-bold text-white">{t("ce_firmar")}</h3>
                <p className="mt-2 text-sm leading-relaxed text-surface-400">
                  {t("ce_wallet_aprobara")}
                </p>
              </div>
              {billeteraNoDisponible ? (
                <div className="rounded-lg border border-amber-500/25 bg-amber-500/[0.06] p-4">
                  <p className="text-xs font-bold text-amber-300">{t("ce_no_en_escritorio")}</p>
                  <p className="mt-2 text-xs leading-relaxed text-amber-100/70">
                    {t("ce_webview_sin_extensiones")}
                  </p>
                  <ExternalLink href={SOLANA_WALLETS_URL} className="mt-4 inline-flex min-h-11 items-center gap-2 rounded-lg border border-amber-500/30 px-3 text-xs font-bold text-amber-200 hover:bg-amber-500/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-amber-300">
                    Ver wallets en Solana <IconoEnlaceExterno size={14} />
                  </ExternalLink>
                </div>
              ) : (
                <div className="space-y-3 rounded-lg border border-white/10 bg-white/[0.02] p-4">
                  <WalletMultiButton className="!min-h-11 !w-full !rounded-lg !bg-brand-500 !text-xs !font-bold hover:!bg-brand-400" />
                  {publicKey && (
                    <button type="button" onClick={() => void handleWeb3()} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-lg border border-brand-500/40 bg-brand-500/10 px-4 text-xs font-bold uppercase tracking-wider text-brand-400 hover:bg-brand-500/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 active:bg-brand-500/25">
                      <CheckCircle2 size={16} /> Firmar y publicar
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          {step === "create-wallet" && (
            <div className="space-y-5">
              <button type="button" onClick={goBack} className="flex min-h-11 items-center gap-2 text-xs font-bold text-surface-400 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400">
                <ArrowLeft size={15} /> {t("ce_cambiar_metodo")}
              </button>
              <div>
                <h3 className="text-base font-bold text-white">{t("ce_crear_wallet")}</h3>
                <p className="mt-2 text-sm leading-relaxed text-surface-400">
                  {t("ce_no_custodia")}
                </p>
              </div>
              <div className="rounded-lg border border-white/10 bg-black/20 p-4 text-xs leading-relaxed text-surface-400">
                <p className="font-bold text-white">{t("ce_antes_de_continuar")}</p>
                <ul className="mt-3 space-y-2">
                  <li>{t("ce_aviso_dominio")}</li>
                  <li>{t("ce_aviso_frase")}</li>
                  <li>{t("ce_aviso_extensiones")}</li>
                </ul>
              </div>
              <ExternalLink href={SOLANA_WALLETS_URL} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 text-xs font-bold uppercase tracking-wider text-white hover:bg-brand-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white active:bg-brand-600">
                {t("ce_explorar_wallets")} <IconoEnlaceExterno size={15} />
              </ExternalLink>
            </div>
          )}

          {isProcessing && (
            <div aria-live="polite" className="flex min-h-64 flex-col items-center justify-center gap-4 py-8 text-center">
              <ThinkingOrb state="processing" size="md" label={flowLabel()} />
              <p className="max-w-sm text-xs leading-relaxed text-surface-400">{t("ce_no_cierres")}</p>
            </div>
          )}

          {step === "done" && receipt && (
            <div aria-live="polite" className="flex min-h-64 flex-col items-center justify-center gap-4 py-6 text-center">
              <ThinkingOrb state="complete" size="md" label="Comprobante registrado" />
              <p className="max-w-md text-xs leading-relaxed text-surface-400">
                {t("ce_flujo_termino")}
              </p>
              <div className="w-full rounded-lg border border-emerald-500/25 bg-emerald-500/[0.06] p-4 text-left">
                <div className="flex items-center gap-2 text-xs font-bold text-emerald-300"><CheckCircle2 size={15} /> {t("ce_comprobante_creado")}</div>
                <p className="mt-2 break-all font-mono text-[10px] leading-relaxed text-emerald-100/60">{receipt.signature}</p>
              </div>
              <ExternalLink href={urlDelExplorador(receipt.signature, health?.network)} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-white/10 px-4 text-xs font-bold text-white/70 hover:border-brand-500/40 hover:text-brand-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400">
                Ver en Solana Explorer <IconoEnlaceExterno size={14} />
              </ExternalLink>
              <button type="button" onClick={onClose} className="min-h-11 rounded-lg bg-brand-500 px-6 text-xs font-bold uppercase tracking-wider text-white hover:bg-brand-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white active:bg-brand-600">
                {t("c_cerrar")}
              </button>
            </div>
          )}

          {step === "error" && (
            <div className="flex min-h-64 flex-col items-center justify-center gap-4 py-6 text-center">
              <ThinkingOrb state="error" size="md" label={t("ce_no_registrado")} />
              <div role="alert" className="w-full rounded-lg border border-red-500/25 bg-red-500/[0.07] p-4 text-left text-xs leading-relaxed text-red-300">
                {error || t("ce_operacion_fallida")}
              </div>
              <button type="button" onClick={goBack} className="min-h-11 rounded-lg border border-white/10 px-5 text-xs font-bold text-white/70 hover:border-white/20 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 active:bg-white/5">
                {t("ce_elegir_otro")}
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
