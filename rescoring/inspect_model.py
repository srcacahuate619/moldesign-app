import torch


def inspect():
    path = "rescoring/trained_models/rtmscore_model1.pth"
    print(f"Loading checkpoint from: {path}")
    checkpoint = torch.load(path, map_location="cpu")
    
    # Check if it has a 'model_state_dict' key
    state_dict = checkpoint.get("model_state_dict", checkpoint)
    
    print("\nModel weights shape inspection:")
    for key, val in state_dict.items():
        # Print only the encoder, MLP, and output projection shapes to verify dimensions
        if any(x in key for x in ["encoder", "MLP", "z_", "atom_types", "bond_types"]):
            print(f"  {key}: {list(val.shape)}")

if __name__ == "__main__":
    inspect()
