/* Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V4 */
/* Hallmark · component: modal · genre: modern-minimal · theme: MolDesign existing
 * states: default · hover · focus · active · disabled · loading · error · success
 * contrast: pass
 */
"use client";

import React, { useEffect, useId, useRef, useState } from "react";
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
      setError(health?.reason || "Solana devnet no está disponible en este momento.");
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
      if (!prepared.memo) throw new Error("No se pudo generar el memo de integridad.");

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
          : "La prueba de Solana devnet no pudo completarse. El faucet público puede limitar solicitudes.",
      );
      setStep("error");
    }
  };

  const handleWeb3 = async () => {
    if (!publicKey) {
      setError("Conecta tu wallet antes de continuar.");
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

      if (!prepared.memo) throw new Error("No se pudo generar el memo de integridad.");

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
      setError(err instanceof Error ? err.message : "Error al firmar con tu wallet.");
      setStep("error");
    }
  };

  const flowLabel = () => {
    switch (step) {
      case "poc-funding":
        return "Solicitando SOL de prueba en devnet";
      case "poc-signing":
        return "Publicando el memo experimental";
      case "web3-prepare":
        return "Preparando el comprobante";
      case "web3-signing":
        return "Esperando tu aprobación en la wallet";
      case "verifying":
        return "Confirmando la transacción en Solana";
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
                Prueba de concepto en devnet. Los archivos permanecen locales; la red recibe una huella y metadata mínima.
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2 font-mono text-[10px] uppercase tracking-wider">
                <span className="text-surface-400">{health?.network || "comprobando red"}</span>
                <span aria-hidden="true" className="text-surface-700">·</span>
                <span className={health?.available ? "text-emerald-400" : health ? "text-red-400" : "text-surface-400"}>
                  {health?.available ? "devnet accesible" : health ? "devnet no disponible" : "verificando"}
                </span>
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isProcessing}
            aria-label="Cerrar"
            className="grid h-11 w-11 shrink-0 place-items-center rounded-lg text-surface-400 transition-colors hover:bg-white/5 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 active:bg-white/10 disabled:cursor-not-allowed disabled:opacity-30"
          >
            <X size={18} />
          </button>
        </header>

        <div className="overflow-y-auto p-5 sm:p-6">
          {step === "select" && (
            <div className="space-y-3">
              <div className="mb-5 rounded-lg border border-cyan-500/20 bg-cyan-500/[0.05] p-3 text-xs leading-relaxed text-cyan-100/75">
                EXPERIMENTAL · Devnet puede reiniciarse y borrar sus registros. Este POC sólo prueba el flujo técnico; no certifica autoría, prioridad ni validez científica.
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
                    Crea una identidad efímera local, solicita SOL sin valor al faucet y publica un memo real. La clave se descarta al terminar.
                  </span>
                </span>
              </button>

              <button
                type="button"
                onClick={() => setStep("wallet")}
                disabled={billeteraNoDisponible}
                title={billeteraNoDisponible ? "Las wallets sólo están disponibles en el navegador web" : undefined}
                className="group flex w-full items-start gap-4 rounded-lg border border-white/10 bg-white/[0.02] p-4 text-left transition-colors hover:border-white/20 hover:bg-white/[0.04] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 active:bg-white/[0.06]"
              >
                <ChoiceIcon><Wallet size={19} /></ChoiceIcon>
                <span className="min-w-0 flex-1">
                  <span className="font-bold text-white">Tengo una wallet</span>
                  <span className="mt-1 block text-xs leading-relaxed text-surface-400">
                    Tú apruebas la transacción y pagas la comisión. La firma pública queda asociada a tu dirección.
                  </span>
                </span>
              </button>
              {billeteraNoDisponible && (
                <p className="px-2 text-[10px] font-semibold uppercase tracking-wide text-amber-300/80">Sólo navegador web · wallet no disponible en la app de escritorio</p>
              )}

              <button
                type="button"
                onClick={() => setStep("create-wallet")}
                className="group flex w-full items-start gap-4 rounded-lg border border-white/10 bg-white/[0.02] p-4 text-left transition-colors hover:border-white/20 hover:bg-white/[0.04] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 active:bg-white/[0.06]"
              >
                <ChoiceIcon><KeyRound size={19} /></ChoiceIcon>
                <span className="min-w-0 flex-1">
                  <span className="font-bold text-white">Quiero crear una wallet</span>
                  <span className="mt-1 block text-xs leading-relaxed text-surface-400">
                    Consulta wallets compatibles y elige su modelo de custodia. MolDesign nunca solicitará tu frase de recuperación.
                  </span>
                </span>
              </button>
            </div>
          )}

          {step === "poc-confirm" && (
            <div className="space-y-5">
              <button type="button" onClick={goBack} className="flex min-h-11 items-center gap-2 text-xs font-bold text-surface-400 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400">
                <ArrowLeft size={15} /> Cambiar método
              </button>
              <div>
                <h3 className="text-base font-bold text-white">Prueba técnica en Solana devnet</h3>
                <p className="mt-2 text-sm leading-relaxed text-surface-400">
                  Publicará una transacción real en una red de pruebas que puede reiniciarse. No tiene validez oficial, científica ni económica.
                </p>
              </div>
              <dl className="divide-y divide-white/5 rounded-lg border border-white/10 bg-black/20 px-4">
                <div className="flex items-center justify-between gap-4 py-3 text-xs"><dt className="text-surface-400">Fondos</dt><dd className="font-bold text-white">Faucet devnet · sin valor</dd></div>
                <div className="flex items-center justify-between gap-4 py-3 text-xs"><dt className="text-surface-400">Firma</dt><dd className="font-bold text-white">Identidad efímera local</dd></div>
                <div className="flex items-center justify-between gap-4 py-3 text-xs"><dt className="text-surface-400">Red</dt><dd className="font-mono text-white">{health?.network || "—"}</dd></div>
                <div className="flex items-center justify-between gap-4 py-3 text-xs"><dt className="text-surface-400">Datos científicos</dt><dd className="font-bold text-white">Permanecen locales</dd></div>
              </dl>
              {health && !health.available && (
                <div role="alert" className="flex gap-2 rounded-lg border border-red-500/25 bg-red-500/[0.07] p-3 text-xs leading-relaxed text-red-300">
                  <AlertCircle size={16} className="mt-0.5 shrink-0" />
                  {health.reason || "Solana devnet no está disponible."}
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
                <ArrowLeft size={15} /> Cambiar método
              </button>
              <div>
                <h3 className="text-base font-bold text-white">Firmar con mi wallet</h3>
                <p className="mt-2 text-sm leading-relaxed text-surface-400">
                  Tu wallet aprobará el memo de integridad y pagará la comisión de la red seleccionada.
                </p>
              </div>
              {billeteraNoDisponible ? (
                <div className="rounded-lg border border-amber-500/25 bg-amber-500/[0.06] p-4">
                  <p className="text-xs font-bold text-amber-300">No disponible dentro de esta app de escritorio</p>
                  <p className="mt-2 text-xs leading-relaxed text-amber-100/70">
                    El WebView de escritorio no carga extensiones de wallet. Puedes ejecutar el POC con identidad efímera o abrir MolDesign en un navegador compatible para usar tu wallet.
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
                <ArrowLeft size={15} /> Cambiar método
              </button>
              <div>
                <h3 className="text-base font-bold text-white">Crear una wallet propia</h3>
                <p className="mt-2 text-sm leading-relaxed text-surface-400">
                  MolDesign no crea ni custodia claves privadas en esta versión. El directorio oficial de Solana permite comparar wallets por plataforma y modelo de custodia.
                </p>
              </div>
              <div className="rounded-lg border border-white/10 bg-black/20 p-4 text-xs leading-relaxed text-surface-400">
                <p className="font-bold text-white">Antes de continuar</p>
                <ul className="mt-3 space-y-2">
                  <li>· Descarga únicamente desde el dominio oficial del proveedor.</li>
                  <li>· Nunca compartas tu frase de recuperación con MolDesign ni con soporte.</li>
                  <li>· Esta build de escritorio no conecta extensiones; el POC efímero de devnet sí funciona aquí.</li>
                </ul>
              </div>
              <ExternalLink href={SOLANA_WALLETS_URL} className="flex min-h-11 w-full items-center justify-center gap-2 rounded-lg bg-brand-500 px-4 text-xs font-bold uppercase tracking-wider text-white hover:bg-brand-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white active:bg-brand-600">
                Explorar wallets de Solana <IconoEnlaceExterno size={15} />
              </ExternalLink>
            </div>
          )}

          {isProcessing && (
            <div aria-live="polite" className="flex min-h-64 flex-col items-center justify-center gap-4 py-8 text-center">
              <ThinkingOrb state="processing" size="md" label={flowLabel()} />
              <p className="max-w-sm text-xs leading-relaxed text-surface-400">No cierres esta ventana hasta recibir la confirmación de la red.</p>
            </div>
          )}

          {step === "done" && receipt && (
            <div aria-live="polite" className="flex min-h-64 flex-col items-center justify-center gap-4 py-6 text-center">
              <ThinkingOrb state="complete" size="md" label="Comprobante registrado" />
              <p className="max-w-md text-xs leading-relaxed text-surface-400">
                El flujo técnico terminó en devnet. Este registro puede desaparecer si la red de pruebas se reinicia y no constituye certificación.
              </p>
              <div className="w-full rounded-lg border border-emerald-500/25 bg-emerald-500/[0.06] p-4 text-left">
                <div className="flex items-center gap-2 text-xs font-bold text-emerald-300"><CheckCircle2 size={15} /> Comprobante de integridad creado</div>
                <p className="mt-2 break-all font-mono text-[10px] leading-relaxed text-emerald-100/60">{receipt.signature}</p>
              </div>
              <ExternalLink href={urlDelExplorador(receipt.signature, health?.network)} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-white/10 px-4 text-xs font-bold text-white/70 hover:border-brand-500/40 hover:text-brand-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400">
                Ver en Solana Explorer <IconoEnlaceExterno size={14} />
              </ExternalLink>
              <button type="button" onClick={onClose} className="min-h-11 rounded-lg bg-brand-500 px-6 text-xs font-bold uppercase tracking-wider text-white hover:bg-brand-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white active:bg-brand-600">
                Cerrar
              </button>
            </div>
          )}

          {step === "error" && (
            <div className="flex min-h-64 flex-col items-center justify-center gap-4 py-6 text-center">
              <ThinkingOrb state="error" size="md" label="No se pudo registrar" />
              <div role="alert" className="w-full rounded-lg border border-red-500/25 bg-red-500/[0.07] p-4 text-left text-xs leading-relaxed text-red-300">
                {error || "La operación no pudo completarse."}
              </div>
              <button type="button" onClick={goBack} className="min-h-11 rounded-lg border border-white/10 px-5 text-xs font-bold text-white/70 hover:border-white/20 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-400 active:bg-white/5">
                Elegir otro método
              </button>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
