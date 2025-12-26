from transformers import CLIPProcessor, CLIPModel

# This triggers the download and saves it to the default cache directory
model_name = "openai/clip-vit-base-patch32"
print(f"Pre-downloading {model_name}...")
CLIPModel.from_pretrained(model_name)
CLIPProcessor.from_pretrained(model_name)
print("Download complete.")