"""
DAVIS Video Object Segmentation - Quick Evaluation
====================================================
Fast evaluation version for quicker processing with detailed metrics
"""

import os
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from torchvision import transforms, models
from PIL import Image
import json
from pathlib import Path
from datetime import datetime
import logging
from collections import defaultdict
import warnings
import time

warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DAVIS_PATH = 'data/DAVIS test'
OUTPUT_DIR = 'davis_vos_results'
FRAMES_OUTPUT_DIR = os.path.join(OUTPUT_DIR, 'sample_frames')
METRICS_OUTPUT_DIR = os.path.join(OUTPUT_DIR, 'metrics')
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
SAMPLE_SEQUENCES = 5  # Process first 5 sequences for quick evaluation
FRAMES_PER_SEQUENCE = 5  # Sample 5 frames per sequence

# Pascal VOC classes
VOC_CLASSES = [
    'background', 'aeroplane', 'bicycle', 'bird', 'boat', 'bottle', 'bus', 'car',
    'cat', 'chair', 'cow', 'diningtable', 'dog', 'horse', 'motorbike', 'person',
    'pottedplant', 'sheep', 'sofa', 'train', 'tvmonitor'
]

# Color map
np.random.seed(42)
COLORS = np.random.randint(0, 256, (len(VOC_CLASSES), 3))
COLORS[0] = [0, 0, 0]


class DeepLabV3VOS:
    """DeepLabV3 Video Object Segmentation"""
    
    def __init__(self, device=DEVICE):
        self.device = device
        self.model = None
        self.transform = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
        self.load_model()
    
    def load_model(self):
        """Load pre-trained DeepLabV3 ResNet50"""
        logger.info("Loading DeepLabV3 ResNet50...")
        self.model = models.segmentation.deeplabv3_resnet50(
            pretrained=True,
            progress=False
        )
        self.model = self.model.to(self.device)
        self.model.eval()
        logger.info(f"✓ Model loaded on {self.device}")
    
    def preprocess_frame(self, frame, target_size=(512, 512)):
        """Preprocess video frame"""
        original_size = frame.shape[:2]
        
        if len(frame.shape) == 3:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            frame_rgb = cv2.cvtColor(cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR), cv2.COLOR_BGR2RGB)
        
        pil_frame = Image.fromarray(frame_rgb)
        pil_frame_resized = pil_frame.resize(target_size, Image.BILINEAR)
        
        tensor = self.transform(pil_frame_resized).unsqueeze(0)
        tensor = tensor.to(self.device)
        
        return tensor, original_size
    
    def segment_frame(self, frame):
        """Segment a single frame"""
        with torch.no_grad():
            tensor, original_size = self.preprocess_frame(frame)
            
            output = self.model(tensor)
            logits = output['out']
            
            preds = torch.argmax(logits, dim=1).squeeze(0).cpu().numpy()
            
            preds_resized = cv2.resize(
                preds.astype(np.float32),
                (original_size[1], original_size[0]),
                interpolation=cv2.INTER_NEAREST
            ).astype(np.uint8)
            
            probs = F.softmax(logits, dim=1)
            max_probs = torch.max(probs, dim=1)[0].squeeze(0).cpu().numpy()
            max_probs_resized = cv2.resize(
                max_probs,
                (original_size[1], original_size[0]),
                interpolation=cv2.INTER_LINEAR
            )
            
            return preds_resized, max_probs_resized
    
    def colorize_mask(self, mask):
        """Convert class indices to RGB"""
        colored = COLORS[mask]
        return colored.astype(np.uint8)
    
    def create_overlay(self, frame, mask, alpha=0.6):
        """Create overlay visualization"""
        colored_mask = self.colorize_mask(mask)
        overlay = cv2.addWeighted(frame, 1 - alpha, colored_mask, alpha, 0)
        return overlay


def process_sample_sequences(vos_model, num_sequences=SAMPLE_SEQUENCES, frames_per_seq=FRAMES_PER_SEQUENCE):
    """Process a sample of sequences for quick evaluation"""
    
    os.makedirs(FRAMES_OUTPUT_DIR, exist_ok=True)
    os.makedirs(METRICS_OUTPUT_DIR, exist_ok=True)
    
    davis_images_path = os.path.join(DAVIS_PATH, 'JPEGImages', 'Full-Resolution')
    sequences = sorted([d for d in os.listdir(davis_images_path) 
                       if os.path.isdir(os.path.join(davis_images_path, d))])
    
    sequences = sequences[:num_sequences]
    logger.info(f"Processing {len(sequences)} sample sequences from DAVIS")
    
    all_results = {}
    summary_stats = {
        'timestamp': datetime.now().isoformat(),
        'total_sequences_sampled': len(sequences),
        'frames_per_sequence': frames_per_seq,
        'total_frames_processed': 0,
        'sequences': {}
    }
    
    start_time = time.time()
    
    for seq_idx, sequence in enumerate(sequences, 1):
        seq_path = os.path.join(davis_images_path, sequence)
        frame_files = sorted([f for f in os.listdir(seq_path) if f.endswith(('.jpg', '.png', '.jpeg'))])
        
        if not frame_files:
            continue
        
        # Sample frames evenly distributed
        if len(frame_files) > frames_per_seq:
            indices = np.linspace(0, len(frame_files) - 1, frames_per_seq, dtype=int)
            sampled_frames = [frame_files[i] for i in indices]
        else:
            sampled_frames = frame_files
        
        seq_results = {
            'sequence': sequence,
            'total_frames_in_video': len(frame_files),
            'frames_processed': len(sampled_frames),
            'frames': [],
            'metrics': {}
        }
        
        confidences = []
        class_distributions = defaultdict(int)
        
        for frame_idx, frame_file in enumerate(sampled_frames):
            frame_path = os.path.join(seq_path, frame_file)
            frame = cv2.imread(frame_path)
            
            if frame is None:
                continue
            
            mask, confidence = vos_model.segment_frame(frame)
            
            # Save outputs
            seq_frames_dir = os.path.join(FRAMES_OUTPUT_DIR, sequence)
            os.makedirs(seq_frames_dir, exist_ok=True)
            
            # Save mask
            mask_path = os.path.join(seq_frames_dir, f"{frame_idx:02d}_mask.png")
            cv2.imwrite(mask_path, mask)
            
            # Save overlay
            overlay = vos_model.create_overlay(frame, mask, alpha=0.5)
            overlay_path = os.path.join(seq_frames_dir, f"{frame_idx:02d}_overlay.png")
            cv2.imwrite(overlay_path, overlay)
            
            # Save colored segmentation
            colored_seg = vos_model.colorize_mask(mask)
            colored_path = os.path.join(seq_frames_dir, f"{frame_idx:02d}_segmentation.png")
            cv2.imwrite(colored_path, cv2.cvtColor(colored_seg, cv2.COLOR_RGB2BGR))
            
            # Compute metrics
            unique_classes, counts = np.unique(mask, return_counts=True)
            for cls_id, count in zip(unique_classes, counts):
                if cls_id < len(VOC_CLASSES):
                    class_distributions[VOC_CLASSES[cls_id]] += int(count)
            
            confidences.append(float(np.mean(confidence)))
            seq_results['frames'].append({
                'frame': frame_file,
                'mask': mask_path,
                'overlay': overlay_path,
                'confidence': float(np.mean(confidence))
            })
        
        # Compute sequence metrics
        seq_results['metrics'] = {
            'avg_confidence': float(np.mean(confidences)) if confidences else 0.0,
            'std_confidence': float(np.std(confidences)) if len(confidences) > 1 else 0.0,
            'classes_detected': len(unique_classes),
            'class_distribution': dict(class_distributions)
        }
        
        all_results[sequence] = seq_results
        summary_stats['total_frames_processed'] += len(sampled_frames)
        summary_stats['sequences'][sequence] = {
            'frames_in_video': len(frame_files),
            'frames_sampled': len(sampled_frames),
            'avg_confidence': seq_results['metrics']['avg_confidence'],
            'classes_detected': seq_results['metrics']['classes_detected']
        }
        
        logger.info(f"[{seq_idx}/{len(sequences)}] ✓ {sequence}: "
                   f"Avg Conf: {seq_results['metrics']['avg_confidence']:.3f}, "
                   f"Classes: {seq_results['metrics']['classes_detected']}")
    
    elapsed_time = time.time() - start_time
    summary_stats['processing_time_seconds'] = elapsed_time
    
    # Save results
    results_path = os.path.join(METRICS_OUTPUT_DIR, 'vos_results.json')
    with open(results_path, 'w') as f:
        json.dump(all_results, f, indent=2, default=str)
    
    summary_path = os.path.join(METRICS_OUTPUT_DIR, 'summary.json')
    with open(summary_path, 'w') as f:
        json.dump(summary_stats, f, indent=2)
    
    logger.info(f"\n✓ Results saved to {METRICS_OUTPUT_DIR}")
    logger.info(f"✓ Segmented frames saved to {FRAMES_OUTPUT_DIR}")
    
    return all_results, summary_stats


def print_summary(summary_stats, all_results):
    """Print formatted summary"""
    print("\n" + "="*80)
    print("DAVIS VIDEO OBJECT SEGMENTATION - DEEPLABV3 EVALUATION SUMMARY")
    print("="*80)
    print(f"\nTimestamp: {summary_stats.get('timestamp', 'N/A')}")
    print(f"Device: {DEVICE}")
    print(f"\nDataset Statistics:")
    print(f"  • Total Sequences Sampled: {summary_stats['total_sequences_sampled']}")
    print(f"  • Frames per Sequence: {summary_stats['frames_per_sequence']}")
    print(f"  • Total Frames Processed: {summary_stats['total_frames_processed']}")
    print(f"  • Processing Time: {summary_stats.get('processing_time_seconds', 0):.2f}s")
    print(f"  • Avg Time per Frame: {summary_stats.get('processing_time_seconds', 0) / max(summary_stats['total_frames_processed'], 1):.2f}s")
    
    print(f"\nSegmentation Results:")
    print(f"{'Sequence':<25} {'Frames':<12} {'Avg Conf':<12} {'Classes':<10}")
    print("-" * 60)
    
    for seq_name, stats in summary_stats['sequences'].items():
        print(f"{seq_name:<25} {stats['frames_sampled']:<12} "
              f"{stats['avg_confidence']:<12.3f} {stats['classes_detected']:<10}")
    
    print("\n" + "="*80)
    print(f"Output Directories:")
    print(f"  • Segmented Frames: {FRAMES_OUTPUT_DIR}/")
    print(f"  • Metrics: {METRICS_OUTPUT_DIR}/")
    print("="*80 + "\n")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("DAVIS Video Object Segmentation - DeepLabV3 (Quick Evaluation)")
    print("="*80 + "\n")
    
    vos_model = DeepLabV3VOS(device=DEVICE)
    all_results, summary_stats = process_sample_sequences(
        vos_model,
        num_sequences=SAMPLE_SEQUENCES,
        frames_per_seq=FRAMES_PER_SEQUENCE
    )
    
    print_summary(summary_stats, all_results)
