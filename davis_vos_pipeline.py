"""
DAVIS Video Object Segmentation Pipeline using DeepLabV3
=========================================================
Performs semantic segmentation on video frames from DAVIS test dataset.
Uses pre-trained DeepLabV3 for unsupervised video object segmentation.
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

warnings.filterwarnings('ignore')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ===== Configuration =====
DAVIS_PATH = 'data/DAVIS test'
OUTPUT_DIR = 'davis_vos_results'
FRAMES_OUTPUT_DIR = os.path.join(OUTPUT_DIR, 'segmented_frames')
VIDEOS_OUTPUT_DIR = os.path.join(OUTPUT_DIR, 'segmented_videos')
METRICS_OUTPUT_DIR = os.path.join(OUTPUT_DIR, 'metrics')
DEVICE = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

# Pascal VOC classes (21 classes)
VOC_CLASSES = [
    'background', 'aeroplane', 'bicycle', 'bird', 'boat', 'bottle', 'bus', 'car',
    'cat', 'chair', 'cow', 'diningtable', 'dog', 'horse', 'motorbike', 'person',
    'pottedplant', 'sheep', 'sofa', 'train', 'tvmonitor'
]

# Color map for visualization (random colors for each class)
np.random.seed(42)
COLORS = np.random.randint(0, 256, (len(VOC_CLASSES), 3))
COLORS[0] = [0, 0, 0]  # Background black


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
        logger.info(f"DeepLabV3 loaded on {device}")
    
    def load_model(self):
        """Load pre-trained DeepLabV3 ResNet50"""
        self.model = models.segmentation.deeplabv3_resnet50(
            pretrained=True,
            progress=True
        )
        self.model = self.model.to(self.device)
        self.model.eval()
        logger.info("DeepLabV3 ResNet50 model loaded successfully")
    
    def preprocess_frame(self, frame, target_size=(512, 512)):
        """Preprocess video frame"""
        original_size = frame.shape[:2]
        
        # Convert BGR to RGB
        if len(frame.shape) == 3:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        else:
            frame_rgb = cv2.cvtColor(cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR), cv2.COLOR_BGR2RGB)
        
        # Convert to PIL and resize
        pil_frame = Image.fromarray(frame_rgb)
        pil_frame_resized = pil_frame.resize(target_size, Image.BILINEAR)
        
        # Apply transforms
        tensor = self.transform(pil_frame_resized).unsqueeze(0)
        tensor = tensor.to(self.device)
        
        return tensor, original_size, (frame_rgb, pil_frame)
    
    def segment_frame(self, frame):
        """
        Segment a single frame using DeepLabV3
        Returns segmentation mask and logits
        """
        with torch.no_grad():
            tensor, original_size, originals = self.preprocess_frame(frame)
            
            # Forward pass
            output = self.model(tensor)
            logits = output['out']
            
            # Get predictions
            preds = torch.argmax(logits, dim=1).squeeze(0).cpu().numpy()
            
            # Resize to original size
            preds_resized = cv2.resize(
                preds.astype(np.float32),
                (original_size[1], original_size[0]),
                interpolation=cv2.INTER_NEAREST
            ).astype(np.uint8)
            
            # Get confidence scores
            probs = F.softmax(logits, dim=1)
            max_probs = torch.max(probs, dim=1)[0].squeeze(0).cpu().numpy()
            max_probs_resized = cv2.resize(
                max_probs,
                (original_size[1], original_size[0]),
                interpolation=cv2.INTER_LINEAR
            )
            
            return preds_resized, max_probs_resized, original_size
    
    def colorize_mask(self, mask):
        """Convert class indices to RGB image"""
        colored = COLORS[mask]
        return colored.astype(np.uint8)
    
    def create_overlay(self, frame, mask, alpha=0.6):
        """Create overlay of segmentation on original frame"""
        colored_mask = self.colorize_mask(mask)
        overlay = cv2.addWeighted(frame, 1 - alpha, colored_mask, alpha, 0)
        return overlay
    
    def create_class_mask(self, mask, class_id):
        """Create binary mask for specific class"""
        binary_mask = (mask == class_id).astype(np.uint8) * 255
        return binary_mask
    
    def segment_video_sequence(self, video_path, sequence_name, max_frames=None):
        """
        Segment all frames in a video sequence
        Returns list of segmentation masks and metrics
        """
        logger.info(f"Processing sequence: {sequence_name}")
        
        # Get frame files
        frame_files = sorted([f for f in os.listdir(video_path) if f.endswith(('.jpg', '.png', '.jpeg'))])
        
        if max_frames:
            frame_files = frame_files[:max_frames]
        
        if not frame_files:
            logger.warning(f"No frames found in {video_path}")
            return None
        
        results = {
            'sequence': sequence_name,
            'total_frames': len(frame_files),
            'masks': [],
            'confidences': [],
            'class_distributions': [],
            'metrics': {}
        }
        
        # Process frames
        for idx, frame_file in enumerate(frame_files):
            frame_path = os.path.join(video_path, frame_file)
            frame = cv2.imread(frame_path)
            
            if frame is None:
                logger.warning(f"Failed to read frame: {frame_file}")
                continue
            
            # Segment frame
            mask, confidence, orig_size = self.segment_frame(frame)
            
            # Save segmented frame
            seq_frames_dir = os.path.join(FRAMES_OUTPUT_DIR, sequence_name)
            os.makedirs(seq_frames_dir, exist_ok=True)
            
            # Save mask
            mask_path = os.path.join(seq_frames_dir, f"{idx:05d}_mask.png")
            cv2.imwrite(mask_path, mask)
            
            # Save overlay
            overlay = self.create_overlay(frame, mask, alpha=0.5)
            overlay_path = os.path.join(seq_frames_dir, f"{idx:05d}_overlay.png")
            cv2.imwrite(overlay_path, overlay)
            
            # Save colored segmentation
            colored_seg = self.colorize_mask(mask)
            colored_path = os.path.join(seq_frames_dir, f"{idx:05d}_segmentation.png")
            cv2.imwrite(colored_path, cv2.cvtColor(colored_seg, cv2.COLOR_RGB2BGR))
            
            # Compute class distribution
            unique_classes, counts = np.unique(mask, return_counts=True)
            class_dist = {}
            for cls_id, count in zip(unique_classes, counts):
                if cls_id < len(VOC_CLASSES):
                    class_dist[VOC_CLASSES[cls_id]] = int(count)
            
            results['masks'].append(mask_path)
            results['confidences'].append(float(np.mean(confidence)))
            results['class_distributions'].append(class_dist)
            
            if (idx + 1) % 10 == 0 or idx == 0:
                logger.info(f"  {sequence_name}: Processed frame {idx + 1}/{len(frame_files)}")
        
        # Compute sequence-level metrics
        results['metrics'] = self._compute_sequence_metrics(results)
        
        return results
    
    def _compute_sequence_metrics(self, results):
        """Compute metrics for the entire sequence"""
        metrics = {
            'avg_confidence': float(np.mean(results['confidences'])),
            'std_confidence': float(np.std(results['confidences'])),
            'min_confidence': float(np.min(results['confidences'])),
            'max_confidence': float(np.max(results['confidences'])),
            'frames_processed': len(results['masks'])
        }
        
        # Aggregate class distributions
        all_classes = defaultdict(list)
        for dist in results['class_distributions']:
            for cls_name, count in dist.items():
                all_classes[cls_name].append(count)
        
        # Get average class presence
        class_presence = {}
        for cls_name, counts in all_classes.items():
            class_presence[cls_name] = {
                'avg_pixels': float(np.mean(counts)),
                'max_pixels': int(np.max(counts)),
                'presence_ratio': float(len(counts) / len(results['class_distributions']))
            }
        
        metrics['class_presence'] = class_presence
        
        return metrics


class DAVISEvaluator:
    """Evaluate VOS results on DAVIS dataset"""
    
    def __init__(self):
        self.dataset_metrics = {}
    
    def compute_miou(self, pred_mask, gt_mask, num_classes=21):
        """Compute mean IoU (if ground truth available)"""
        ious = []
        for cls_id in range(num_classes):
            pred_binary = (pred_mask == cls_id).astype(np.uint8)
            gt_binary = (gt_mask == cls_id).astype(np.uint8)
            
            intersection = np.sum(pred_binary & gt_binary)
            union = np.sum(pred_binary | gt_binary)
            
            if union > 0:
                iou = intersection / union
                ious.append(iou)
        
        return np.mean(ious) if ious else 0.0
    
    def compute_boundary_iou(self, pred_mask, gt_mask, thickness=5):
        """Compute boundary-based IoU metric"""
        # Create boundary masks
        pred_boundary = cv2.dilate(
            cv2.Canny(pred_mask.astype(np.uint8), 0, 1),
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (thickness, thickness))
        )
        
        gt_boundary = cv2.dilate(
            cv2.Canny(gt_mask.astype(np.uint8), 0, 1),
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (thickness, thickness))
        )
        
        intersection = np.sum(pred_boundary & gt_boundary)
        union = np.sum(pred_boundary | gt_boundary)
        
        return intersection / union if union > 0 else 0.0


def create_video_from_frames(frame_dir, output_video_path, fps=24):
    """Create video from segmented frames"""
    frame_files = sorted([f for f in os.listdir(frame_dir) if '_overlay.png' in f])
    
    if not frame_files:
        logger.warning(f"No overlay frames found in {frame_dir}")
        return False
    
    first_frame = cv2.imread(os.path.join(frame_dir, frame_files[0]))
    height, width = first_frame.shape[:2]
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter(output_video_path, fourcc, fps, (width, height))
    
    for frame_file in frame_files:
        frame = cv2.imread(os.path.join(frame_dir, frame_file))
        out.write(frame)
    
    out.release()
    logger.info(f"Video saved: {output_video_path}")
    return True


def main():
    """Main pipeline"""
    print("\n" + "="*70)
    print("DAVIS Video Object Segmentation Pipeline - DeepLabV3")
    print("="*70 + "\n")
    
    # Create output directories
    os.makedirs(FRAMES_OUTPUT_DIR, exist_ok=True)
    os.makedirs(VIDEOS_OUTPUT_DIR, exist_ok=True)
    os.makedirs(METRICS_OUTPUT_DIR, exist_ok=True)
    
    # Initialize VOS model
    vos_model = DeepLabV3VOS(device=DEVICE)
    
    # Get video sequences
    davis_images_path = os.path.join(DAVIS_PATH, 'JPEGImages', 'Full-Resolution')
    sequences = sorted([d for d in os.listdir(davis_images_path) 
                       if os.path.isdir(os.path.join(davis_images_path, d))])
    
    logger.info(f"Found {len(sequences)} video sequences in DAVIS dataset")
    
    # Process all sequences
    all_results = {}
    summary_stats = {
        'total_sequences': len(sequences),
        'total_frames_processed': 0,
        'sequences': {}
    }
    
    for seq_idx, sequence in enumerate(sequences, 1):
        seq_path = os.path.join(davis_images_path, sequence)
        
        try:
            # Segment sequence
            results = vos_model.segment_video_sequence(seq_path, sequence)
            
            if results:
                all_results[sequence] = results
                summary_stats['total_frames_processed'] += results['total_frames']
                summary_stats['sequences'][sequence] = {
                    'frames': results['total_frames'],
                    'avg_confidence': results['metrics'].get('avg_confidence', 0),
                    'classes_detected': len(results['metrics'].get('class_presence', {}))
                }
                
                # Create video from frames
                frames_dir = os.path.join(FRAMES_OUTPUT_DIR, sequence)
                video_path = os.path.join(VIDEOS_OUTPUT_DIR, f"{sequence}_segmentation.mp4")
                create_video_from_frames(frames_dir, video_path, fps=24)
                
                logger.info(f"[{seq_idx}/{len(sequences)}] ✓ {sequence}: "
                          f"{results['total_frames']} frames, "
                          f"Avg Conf: {results['metrics']['avg_confidence']:.3f}")
            
        except Exception as e:
            logger.error(f"Error processing sequence {sequence}: {str(e)}")
            summary_stats['sequences'][sequence] = {'status': 'FAILED', 'error': str(e)}
    
    # Save results
    results_path = os.path.join(METRICS_OUTPUT_DIR, 'vos_results.json')
    with open(results_path, 'w') as f:
        # Convert numpy types for JSON serialization
        json_results = json.dumps(all_results, default=str, indent=2)
        f.write(json_results)
    
    # Save summary
    summary_path = os.path.join(METRICS_OUTPUT_DIR, 'summary.json')
    with open(summary_path, 'w') as f:
        json.dump(summary_stats, f, indent=2)
    
    logger.info(f"\nResults saved to {METRICS_OUTPUT_DIR}")
    
    # Print summary
    print("\n" + "="*70)
    print("DAVIS VOS PIPELINE SUMMARY")
    print("="*70)
    print(f"Total Sequences Processed: {len(all_results)}/{len(sequences)}")
    print(f"Total Frames Processed: {summary_stats['total_frames_processed']}")
    print(f"Success Rate: {len(all_results)/len(sequences)*100:.1f}%")
    print("="*70 + "\n")
    
    return all_results, summary_stats


if __name__ == '__main__':
    all_results, summary = main()
