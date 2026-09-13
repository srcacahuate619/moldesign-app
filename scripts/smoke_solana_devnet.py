#!/usr/bin/env python3
"""Read-only smoke test for MolDesign's experimental Solana devnet boundary.

This does not create a transaction, request funds, or certify scientific data.
The end-to-end state-changing POC is initiated explicitly from the app UI.
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib import request

RPC_URL = "https://api.devnet.solana.com"


def rpc(method: str, params: list | None = None):
    payload = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params or []}
    ).encode("utf-8")
    req = request.Request(
        RPC_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "MolDesign/1.0-devnet-smoke"},
        method="POST",
    )
    with request.urlopen(req, timeout=15) as response:
        document = json.loads(response.read().decode("utf-8"))
    if document.get("error"):
        raise RuntimeError(document["error"])
    return document.get("result")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--signature",
        help="Optional devnet transaction signature to confirm is retrievable.",
    )
    args = parser.parse_args()

    health = rpc("getHealth")
    version = rpc("getVersion")
    blockhash = rpc(
        "getLatestBlockhash",
        [{"commitment": "confirmed"}],
    )
    if health != "ok" or not blockhash or not blockhash.get("value", {}).get("blockhash"):
        raise RuntimeError("Solana devnet did not return a healthy confirmed blockhash")

    result = {
        "status": "SMOKE_OK",
        "network": "devnet",
        "experimental": True,
        "official_validity": False,
        "state_changed": False,
        "solana_core": version.get("solana-core") if isinstance(version, dict) else None,
        "confirmed_blockhash": blockhash["value"]["blockhash"],
    }
    if args.signature:
        tx = rpc(
            "getTransaction",
            [
                args.signature,
                {
                    "encoding": "jsonParsed",
                    "commitment": "confirmed",
                    "maxSupportedTransactionVersion": 0,
                },
            ],
        )
        result["signature_retrievable"] = tx is not None
        if tx is None:
            raise RuntimeError("The supplied signature was not found on devnet")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "SMOKE_FAILED",
                    "network": "devnet",
                    "experimental": True,
                    "error": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)
