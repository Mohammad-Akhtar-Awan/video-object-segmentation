import os
import torch
import numpy as np
from mmseg.apis import MMSegInferencer
from mmseg.utils import register_all_modules
from PIL import Image

# --- Configuration ---
# You need a valid configuration file and a pre-trained checkpoint.
# We use the DeepLabV3+ model with a ResNet-101 backbone trained on the Cityscapes dataset,
# which is a common, robust semantic segmentation model.

# NOTE: Replace these paths with your actual local file paths!
# 1. Config file (from the mmsegmentation/configs directory)
config_file = 'configs/deeplabv3plus/deeplabv3plus_r101-d8_4xb4-80k_cityscapes.py'

# 2. Checkpoint path (You must download this file from the OpenMMLab model zoo)
# Example checkpoint for the config above:
# 'https://download.openmmlab.com/mmsegmentation/v0.5/deeplabv3plus/deeplabv3plus_r101-d8_512x1024_80k_cityscapes/deeplabv3plus_r101-d8_512x1024_80k_cityscapes_20201227_193539-c1249767.pth'
checkpoint_file = 'checkpoints/deeplabv3plus_r101_cityscapes_80k.pth' 

# 3. Input images for inference
input_image_paths = [
    'data/test_image_1.jpg',
    'data/test_image_2.png'
]

# 4. Output directory to save the visualized results
output_dir = 'mmseg_inference_results'

# 5. Check device availability
device = 'cuda:0' if torch.cuda.is_available() else 'cpu'

# --- Utility Function: Placeholder Image Generation ---
def generate_placeholder_image(filepath, size=(512, 512)):
    """Creates a dummy image if the file doesn't exist, for demonstration purposes."""
    if not os.path.exists(filepath):
        print(f"    -> NOTE: Generating placeholder image at {filepath}")
        if not os.path.isdir(os.path.dirname(filepath)):
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
        # Create a simple grayscale image
        img = Image.fromarray(np.random.randint(0, 256, size, dtype=np.uint8))
        img.save(filepath)
        return True
    return False

# --- Main Inference Function ---
def run_mmseg_inference():
    # Register all modules required by MMSegmentation
    register_all_modules()

    # 1. Prepare Environment (Create dummy images if needed)
    os.makedirs(output_dir, exist_ok=True)
    for path in input_image_paths:
        generate_placeholder_image(path)

    if not os.path.exists(checkpoint_file):
        print(f"\n[ERROR] Checkpoint file not found: {checkpoint_file}")
        print("Please download the checkpoint for the specified model and place it in the correct location.")
        return

    print(f"--- Starting Inference on {device} ---")
    print(f"Model Config: {config_file}")
    
    # 2. Initialize the Inferencer
    try:
        inferencer = MMSegInferencer(
            model=config_file,
            weights=checkpoint_file,
            device=device
        )
    except Exception as e:
        print(f"\n[ERROR] Failed to initialize MMSegInferencer. Check your config path and environment setup.")
        print(f"Details: {e}")
        return

    print("Inferencer initialized successfully.")

    # 3. Run Inference on the list of images
    try:
        # The visualize=True parameter tells the inferencer to save an image
        # where the prediction mask is overlaid onto the original image.
        inferencer(
            img=input_image_paths,
            out_dir=output_dir,
            save_vis=True,        # Save the visualization (mask + original image)
            save_pred=True        # Save the raw prediction mask (single-channel image)
        )
        print("\n--- Inference Complete ---")
        print(f"Results (Predicted masks and visualizations) saved to: {output_dir}")

    except Exception as e:
        print(f"\n[ERROR] An error occurred during inference. Check input paths or model loading.")
        print(f"Details: {e}")


if __name__ == '__main__':
    # Ensure you replace 'checkpoints/deeplabv3plus_r101_cityscapes_80k.pth'
    # with a valid, downloaded checkpoint file before running this script.
    # The config file path must also be correct relative to your current working directory.
    run_mmseg_inference()