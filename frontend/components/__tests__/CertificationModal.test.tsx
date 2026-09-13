import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { setTauriEnv } from "../../vitest.setup";
import { CertificationModal } from "../CertificationModal";

const mocks = vi.hoisted(() => ({
  checkBlockchainHealth: vi.fn(),
  prepareCertification: vi.fn(),
  linkCertification: vi.fn(),
  sendAndConfirmTransaction: vi.fn(),
  requestAirdrop: vi.fn(),
  confirmTransaction: vi.fn(),
}));

vi.mock("../../lib/api", () => ({
  checkBlockchainHealth: (...args: unknown[]) => mocks.checkBlockchainHealth(...args),
  linkCertification: (...args: unknown[]) => mocks.linkCertification(...args),
  prepareCertification: (...args: unknown[]) => mocks.prepareCertification(...args),
}));

vi.mock("@solana/web3.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@solana/web3.js")>();
  return {
    ...actual,
    sendAndConfirmTransaction: (...args: unknown[]) => mocks.sendAndConfirmTransaction(...args),
  };
});

vi.mock("@solana/wallet-adapter-react", () => ({
  useWallet: () => ({ publicKey: null, sendTransaction: vi.fn() }),
  useConnection: () => ({
    connection: {
      requestAirdrop: (...args: unknown[]) => mocks.requestAirdrop(...args),
      confirmTransaction: (...args: unknown[]) => mocks.confirmTransaction(...args),
    },
  }),
}));

vi.mock("@solana/wallet-adapter-react-ui", () => ({
  WalletMultiButton: () => <button type="button">Conectar wallet</button>,
}));

vi.mock("../ui/ThinkingOrb", () => ({
  ThinkingOrb: ({ label }: { label?: string }) => <div>{label}</div>,
}));

describe("CertificationModal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setTauriEnv(true);
    mocks.checkBlockchainHealth.mockResolvedValue({
      available: true,
      network: "devnet",
      experimental: true,
      official_validity: false,
    });
    mocks.prepareCertification.mockResolvedValue({
      already_certified: false,
      memo: "MolDesign-v1|CC0|" + "a".repeat(64) + "|85.50|7E2Y|2026-09-07T00:00:00+00:00",
    });
    mocks.requestAirdrop.mockResolvedValue("airdrop-test-123");
    mocks.confirmTransaction.mockResolvedValue({ value: { err: null } });
    mocks.sendAndConfirmTransaction.mockResolvedValue("tx-test-123");
    mocks.linkCertification.mockResolvedValue({ success: true, signature: "tx-test-123" });
  });

  it("ejecuta una transacción devnet real sólo tras confirmación explícita", async () => {
    const onSuccess = vi.fn();
    render(
      <CertificationModal moleculeId="mol-1" onClose={vi.fn()} onSuccess={onSuccess} />,
    );

    expect(screen.getByRole("button", { name: /Ejecutar prueba devnet/i })).toBeInTheDocument();
    expect(screen.getByText(/no certifica autoría, prioridad ni validez científica/i)).toBeInTheDocument();
    expect(mocks.prepareCertification).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /Ejecutar prueba devnet/i }));
    expect(await screen.findByRole("button", { name: /Ejecutar POC/i })).toBeEnabled();
    expect(mocks.requestAirdrop).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /Ejecutar POC/i }));

    await waitFor(() => expect(mocks.requestAirdrop).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mocks.sendAndConfirmTransaction).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(mocks.linkCertification).toHaveBeenCalledWith("mol-1", "tx-test-123"));
    expect(onSuccess).toHaveBeenCalledWith({ signature: "tx-test-123", signer: "experimental" });
    expect(await screen.findByText(/Comprobante de integridad creado/i)).toBeInTheDocument();
  });

  it("bloquea la wallet en escritorio pero mantiene disponible el POC efímero", async () => {
    render(
      <CertificationModal moleculeId="mol-1" onClose={vi.fn()} onSuccess={vi.fn()} />,
    );

    const walletButton = screen.getByRole("button", { name: /Tengo una wallet/i });
    expect(walletButton).toBeDisabled();
    expect(screen.getByText(/wallet no disponible en la app de escritorio/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ejecutar prueba devnet/i })).toBeEnabled();

    fireEvent.click(screen.getByRole("button", { name: /Quiero crear una wallet/i }));
    expect(await screen.findByText(/MolDesign no crea ni custodia claves privadas/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Explorar wallets de Solana/i })).toHaveAttribute(
      "href",
      "https://solana.com/wallets",
    );
  });
});
