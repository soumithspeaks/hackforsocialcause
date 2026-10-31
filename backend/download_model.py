from transformers import Qwen2_5_VLForConditionalGeneration, AutoProcessor

print("Downloading Qwen2.5-VL 3B model (approx 2GB for 4-bit version)...")
print("This may take a few minutes depending on your internet connection.")

# The model and processor will be downloaded and cached in ~/.cache/huggingface/hub
model = Qwen2_5_VLForConditionalGeneration.from_pretrained(
    "Qwen/Qwen2.5-VL-3B-Instruct",
    device_map="auto"
)
processor = AutoProcessor.from_pretrained("Qwen/Qwen2.5-VL-3B-Instruct")

print("Download complete! You can now start the backend with AVRA_USE_REAL_VLM=true")
