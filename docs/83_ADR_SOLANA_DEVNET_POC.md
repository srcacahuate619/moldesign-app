# ADR 83 — Solana devnet como prueba de concepto

**Estado:** aceptado para `v1.0.0-alpha`  
**Alcance:** experimental, sin validez oficial, científica, económica ni de prioridad.

## Decisión

MolDesign conserva una integración real con Solana exclusivamente sobre
**devnet**. La red sólo recibe un Memo Program con la huella y metadatos mínimos
del expediente. No recibe los archivos científicos.

Hay dos caminos de firma:

1. En navegador, la wallet del investigador firma y paga.
2. En escritorio, el POC genera una identidad efímera dentro del WebView,
   solicita SOL sin valor al faucet de devnet, firma un único memo y descarta la
   clave. No es una identidad institucional ni persistente.

El backend no firma. Prepara el memo y verifica la transacción confirmada por
JSON-RPC estándar. El endpoint heredado `POST /blockchain/certify` responde
`409` para que ningún cliente pueda confundirlo con una firma institucional.

## Motivo de la frontera

La cadena Python `solana → solders → jsonalias==0.1.1` introducía un paquete
sin licencia declarada en el runtime redistribuido. No era necesaria: la firma
ya pertenecía al frontend y la consulta de `getHealth`/`getTransaction` cabe
en JSON-RPC. Se retiraron las tres dependencias del runtime y de sus locks.

El frontend conserva `@solana/web3.js` y su dependencia transitiva
`rpc-websockets` (LGPL-3.0-only). Sus avisos, licencia y vía de reemplazo deben
seguir acompañando el instalador.

## Contrato de honestidad

- Sólo se acepta `https://api.devnet.solana.com`; mainnet se rechaza.
- Devnet puede reiniciarse: el registro puede desaparecer.
- Un memo confirma que ciertos bytes estuvieron en una transacción, no que su
  ciencia sea correcta ni que su firmante tenga prioridad legal.
- La función nunca se ejecuta automáticamente.
- Una transacción sólo se enlaza al expediente local si coinciden hash de
  molécula, target y score redondeado que realmente fueron sellados.

## Verificación

Smoke de red, sin cambiar estado:

```powershell
cd frontend
npm run smoke:solana-devnet
```

La prueba devuelve `SMOKE_OK`, la versión del nodo y un blockhash confirmado.
Puede añadirse `--signature <FIRMA>` al script Python para comprobar que una
transacción creada desde la UI es recuperable.

La prueba end-to-end con escritura se hace desde la ventana de registro:
`Ejecutar prueba devnet → Ejecutar POC`. Está sujeta al rate limit del faucet
público; un rechazo del faucet es indisponibilidad externa, no debe degradar el
pipeline científico local.
