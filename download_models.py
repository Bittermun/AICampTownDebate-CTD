"""
Download GGUF models from Hugging Face.
Recommended models for 8GB VRAM:
- Debater: Mistral-7B-Instruct Q4_K_M (~4.4GB)
- Judge: Phi-3-mini Q4_K_M (~2.2GB) 
"""
import os
import sys
from pathlib import Path

# Hugging Face model URLs (Q4_K_M quantization)
MODELS = {
    "mistral-7b": {
        "url": "https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF/resolve/main/mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        "filename": "mistral-7b-instruct-v0.2.Q4_K_M.gguf",
        "size": "4.4GB",
        "role": "debater",
    },
    "phi-3-mini": {
        "url": "https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf",
        "filename": "Phi-3-mini-4k-instruct-q4.gguf",
        "size": "2.2GB",
        "role": "judge",
    },
    # Smaller alternative for testing
    "qwen2-1.5b": {
        "url": "https://huggingface.co/Qwen/Qwen2-1.5B-Instruct-GGUF/resolve/main/qwen2-1_5b-instruct-q4_k_m.gguf",
        "filename": "qwen2-1_5b-instruct-q4_k_m.gguf",
        "size": "1.0GB",
        "role": "both (small)",
    },
}


def download_model(model_key: str, models_dir: Path):
    """Download a model using requests with progress."""
    try:
        import requests
    except ImportError:
        print("Installing requests...")
        os.system(f"{sys.executable} -m pip install requests")
        import requests
    
    if model_key not in MODELS:
        print(f"Unknown model: {model_key}")
        print(f"Available: {list(MODELS.keys())}")
        return
    
    model = MODELS[model_key]
    target = models_dir / model["filename"]
    
    if target.exists():
        print(f"✓ {model['filename']} already exists")
        return
    
    print(f"Downloading {model['filename']} ({model['size']})...")
    print(f"  From: {model['url']}")
    
    response = requests.get(model["url"], stream=True)
    total = int(response.headers.get("content-length", 0))
    
    with open(target, "wb") as f:
        downloaded = 0
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
            downloaded += len(chunk)
            if total:
                pct = (downloaded / total) * 100
                print(f"\r  Progress: {pct:.1f}%", end="", flush=True)
    
    print(f"\n✓ Saved to {target}")


def main():
    models_dir = Path(__file__).parent / "models"
    models_dir.mkdir(exist_ok=True)
    
    print("=" * 50)
    print("TOKEN-DEBATE MODEL DOWNLOADER")
    print("=" * 50)
    print(f"\nModels will be saved to: {models_dir}")
    print("\nAvailable models:")
    for key, info in MODELS.items():
        print(f"  {key}: {info['filename']} ({info['size']}) - {info['role']}")
    
    if len(sys.argv) > 1:
        # Download specific model
        for model_key in sys.argv[1:]:
            download_model(model_key, models_dir)
    else:
        # Interactive selection
        print("\nOptions:")
        print("  1. Download recommended pair (Mistral-7B + Phi-3-mini)")
        print("  2. Download small test model (Qwen2-1.5B)")
        print("  3. Exit")
        
        choice = input("\nSelect [1/2/3]: ").strip()
        
        if choice == "1":
            download_model("mistral-7b", models_dir)
            download_model("phi-3-mini", models_dir)
        elif choice == "2":
            download_model("qwen2-1.5b", models_dir)
        else:
            print("Exiting.")


if __name__ == "__main__":
    main()
