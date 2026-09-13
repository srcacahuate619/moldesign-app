#!/usr/bin/env python3
"""Verify checkpoint format for CLGNN fixed model."""
import torch

path = r"D:\moldesign-build\rescoring\artifacts\gnn_v2_cl_best.pt"
ck = torch.load(path, map_location="cpu", weights_only=False)
print(f"Checkpoint type: {type(ck).__name__}")
print(f"Has prot_encoder.in_proj.weight: {'prot_encoder.in_proj.weight' in ck}")
print(f"Has model_state_dict key: {'model_state_dict' in ck}")

if "model_state_dict" in ck:
    sd = ck["model_state_dict"]
    print(f"  model_state_dict type: {type(sd).__name__}")
    print(f"  Keys in sd: {list(sd.keys())[:3]}")
else:
    # Its a raw state dict
    lip = ck["lig_encoder.in_proj.weight"]
    pip = ck["prot_encoder.in_proj.weight"]
    print(f"  lig_encoder.in_proj: {lip.shape}")
    print(f"  prot_encoder.in_proj: {pip.shape}")

# Also verify the old finetuned format
old_path = r"D:\moldesign-build\rescoring\artifacts\clgnn_finetuned.pt"
ck_old = torch.load(old_path, map_location="cpu", weights_only=False)
print(f"\nOld checkpoint type: {type(ck_old).__name__}")
old_lip = ck_old.get("lig_encoder.in_proj.weight", ck_old.get("model_state_dict", {}).get("lig_encoder.in_proj.weight") if isinstance(ck_old, dict) else None)
print(f"Old lig_encoder.in_proj: {old_lip.shape if old_lip is not None else 'NOT FOUND'}")
