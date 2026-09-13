"use client";

import React, { useMemo } from "react";
import {
  ConnectionProvider,
  WalletProvider as SolanaWalletProvider,
  type ConnectionProviderProps,
  type WalletProviderProps,
} from "@solana/wallet-adapter-react";
import {
  WalletModalProvider,
  type WalletModalProviderProps,
} from "@solana/wallet-adapter-react-ui";
import { clusterApiUrl } from "@solana/web3.js";
import "../app/vendor/wallet-adapter-react-ui.css";

/**
 * `@solana/wallet-adapter-*` viaja con los tipos de React 18 y este proyecto usa
 * los de React 19. La incompatibilidad es SÓLO en el tipo de retorno del
 * componente —`FC` de React 18 devuelve `ReactElement`, y el `ReactNode` de
 * React 19 ya no lo acepta— y hace que TypeScript los rechace como elementos
 * JSX (TS2786). No es un defecto de este código ni algo que se pueda arreglar
 * aquí: se arregla cuando el paquete actualice sus tipos.
 *
 * Lo que había era `ConnectionProvider as any` × 3, que además de saltarse ese
 * choque apagaba la comprobación de las props: `endpoint`, `wallets` y
 * `autoConnect` dejaban de existir para el compilador.
 *
 * Aquí se convierte sólo el retorno y **se conservan las props del componente
 * original** con `ComponentProps`. Si el paquete cambia el nombre de una prop,
 * esto falla, que es lo que se quiere.
 */
type ComponenteCompatible<P> = (props: P) => React.ReactNode;

const Compat = {
  // Los tipos de props se importan del propio paquete, así que siguen siendo
  // los suyos: sólo se sustituye el tipo de RETORNO, que es donde está el
  // choque. `React.ComponentProps<typeof X>` no sirve aquí porque exige que X
  // ya sea un elemento JSX válido, que es justo lo que falla.
  Connection: ConnectionProvider as unknown as ComponenteCompatible<ConnectionProviderProps>,
  Wallet: SolanaWalletProvider as unknown as ComponenteCompatible<WalletProviderProps>,
  Modal: WalletModalProvider as unknown as ComponenteCompatible<WalletModalProviderProps>,
};

export function WalletProvider({ children }: { children: React.ReactNode }) {
  // Use Devnet for certification
  const network = clusterApiUrl("devnet");
  
  // Wallets are auto-detected by standard, but we can explicitly add more if needed
  const wallets = useMemo(() => [], []);

  return (
    <Compat.Connection endpoint={network}>
      <Compat.Wallet wallets={wallets} autoConnect>
        <Compat.Modal>{children}</Compat.Modal>
      </Compat.Wallet>
    </Compat.Connection>
  );
}
