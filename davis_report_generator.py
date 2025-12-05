"""
DAVIS VOS Analysis and Report Generation
==========================================
Generate comprehensive evaluation metrics and HTML report
"""

import json
import os
import cv2
import numpy as np
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
METRICS_DIR = 'davis_vos_results/metrics'
FRAMES_DIR = 'davis_vos_results/sample_frames'
REPORT_DIR = 'davis_vos_results/reports'

os.makedirs(REPORT_DIR, exist_ok=True)

class VOSAnalyzer:
    """Analyze VOS evaluation results"""
    
    def __init__(self):
        self.results = None
        self.summary = None
        self.load_results()
    
    def load_results(self):
        """Load evaluation results from JSON"""
        results_file = os.path.join(METRICS_DIR, 'vos_results.json')
        summary_file = os.path.join(METRICS_DIR, 'summary.json')
        
        with open(results_file, 'r') as f:
            self.results = json.load(f)
        
        with open(summary_file, 'r') as f:
            self.summary = json.load(f)
        
        logger.info("Loaded evaluation results")
    
    def generate_metrics_report(self):
        """Generate detailed metrics report"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'overview': {
                'total_sequences': self.summary['total_sequences_sampled'],
                'total_frames': self.summary['total_frames_processed'],
                'processing_time': self.summary.get('processing_time_seconds', 0),
                'avg_time_per_frame': self.summary.get('processing_time_seconds', 0) / max(self.summary['total_frames_processed'], 1)
            },
            'sequence_metrics': {},
            'aggregate_metrics': {}
        }
        
        # Per-sequence metrics
        all_confidences = []
        all_classes = []
        
        for seq_name, stats in self.summary['sequences'].items():
            report['sequence_metrics'][seq_name] = {
                'frames_in_video': stats['frames_in_video'],
                'frames_sampled': stats['frames_sampled'],
                'avg_confidence': stats['avg_confidence'],
                'classes_detected': stats['classes_detected']
            }
            all_confidences.append(stats['avg_confidence'])
            all_classes.append(stats['classes_detected'])
        
        # Aggregate metrics
        report['aggregate_metrics'] = {
            'avg_confidence': float(np.mean(all_confidences)),
            'std_confidence': float(np.std(all_confidences)),
            'min_confidence': float(np.min(all_confidences)),
            'max_confidence': float(np.max(all_confidences)),
            'avg_classes_detected': float(np.mean(all_classes)),
            'total_unique_sequences': len(self.summary['sequences'])
        }
        
        # Save report
        report_path = os.path.join(REPORT_DIR, 'metrics_report.json')
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"✓ Metrics report saved: {report_path}")
        return report


def create_html_report():
    """Create interactive HTML report"""
    
    analyzer = VOSAnalyzer()
    metrics = analyzer.generate_metrics_report()
    
    # Collect sample images
    sample_images = {}
    if os.path.exists(FRAMES_DIR):
        for seq_folder in os.listdir(FRAMES_DIR):
            seq_path = os.path.join(FRAMES_DIR, seq_folder)
            if os.path.isdir(seq_path):
                images = sorted([f for f in os.listdir(seq_path) if f.endswith(('.png', '.jpg', '.jpeg'))])
                if images:
                    sample_images[seq_folder] = images[:3]  # First 3 images
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DAVIS VOS - DeepLabV3 Evaluation Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        header {{
            background: white;
            border-radius: 10px;
            padding: 30px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        
        h1 {{
            color: #667eea;
            font-size: 2.5em;
            margin-bottom: 10px;
            text-align: center;
        }}
        
        .subtitle {{
            text-align: center;
            color: #666;
            font-size: 1.1em;
            margin-bottom: 20px;
        }}
        
        .timestamp {{
            text-align: center;
            color: #999;
            font-size: 0.9em;
            margin-top: 20px;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        
        .stat-card {{
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            text-align: center;
        }}
        
        .stat-card h3 {{
            color: #667eea;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}
        
        .stat-value {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }}
        
        .stat-unit {{
            font-size: 0.8em;
            color: #999;
            margin-top: 5px;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }}
        
        th {{
            background: #667eea;
            color: white;
            padding: 15px;
            text-align: left;
            font-weight: 600;
        }}
        
        td {{
            padding: 12px 15px;
            border-bottom: 1px solid #eee;
        }}
        
        tr:hover {{
            background: #f5f5f5;
        }}
        
        .gallery {{
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 30px;
        }}
        
        .gallery h2 {{
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.8em;
        }}
        
        .sequence-gallery {{
            margin-bottom: 40px;
        }}
        
        .sequence-title {{
            font-size: 1.3em;
            color: #333;
            margin: 20px 0 15px 0;
            padding-bottom: 10px;
            border-bottom: 2px solid #667eea;
        }}
        
        .image-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }}
        
        .image-container {{
            background: #f9f9f9;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        
        .image-container img {{
            width: 100%;
            height: auto;
            display: block;
        }}
        
        .image-label {{
            padding: 10px;
            background: #f5f5f5;
            font-size: 0.9em;
            color: #666;
            text-align: center;
        }}
        
        .metrics-section {{
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 30px;
        }}
        
        .metrics-section h2 {{
            color: #667eea;
            margin-bottom: 20px;
            font-size: 1.8em;
        }}
        
        .metric-item {{
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid #eee;
        }}
        
        .metric-item:last-child {{
            border-bottom: none;
        }}
        
        .metric-label {{
            font-weight: 600;
            color: #333;
        }}
        
        .metric-value {{
            color: #667eea;
            font-weight: bold;
        }}
        
        footer {{
            background: rgba(255,255,255,0.1);
            color: white;
            text-align: center;
            padding: 20px;
            border-radius: 10px;
            margin-top: 30px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎬 DAVIS Video Object Segmentation</h1>
            <p class="subtitle">DeepLabV3 Semantic Segmentation Evaluation</p>
            <p class="timestamp">Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Sequences Processed</h3>
                <div class="stat-value">{metrics['overview']['total_sequences']}</div>
                <div class="stat-unit">DAVIS test videos</div>
            </div>
            <div class="stat-card">
                <h3>Frames Analyzed</h3>
                <div class="stat-value">{metrics['overview']['total_frames']}</div>
                <div class="stat-unit">sampled frames</div>
            </div>
            <div class="stat-card">
                <h3>Avg Confidence</h3>
                <div class="stat-value">{metrics['aggregate_metrics']['avg_confidence']:.3f}</div>
                <div class="stat-unit">segmentation confidence</div>
            </div>
            <div class="stat-card">
                <h3>Avg Classes</h3>
                <div class="stat-value">{metrics['aggregate_metrics']['avg_classes_detected']:.1f}</div>
                <div class="stat-unit">per frame</div>
            </div>
        </div>
        
        <div class="metrics-section">
            <h2>📊 Overall Metrics</h2>
            <div class="metric-item">
                <span class="metric-label">Processing Time:</span>
                <span class="metric-value">{metrics['overview']['processing_time']:.2f}s</span>
            </div>
            <div class="metric-item">
                <span class="metric-label">Average Time per Frame:</span>
                <span class="metric-value">{metrics['overview']['avg_time_per_frame']:.2f}s</span>
            </div>
            <div class="metric-item">
                <span class="metric-label">Confidence Std Dev:</span>
                <span class="metric-value">±{metrics['aggregate_metrics']['std_confidence']:.3f}</span>
            </div>
            <div class="metric-item">
                <span class="metric-label">Min Confidence:</span>
                <span class="metric-value">{metrics['aggregate_metrics']['min_confidence']:.3f}</span>
            </div>
            <div class="metric-item">
                <span class="metric-label">Max Confidence:</span>
                <span class="metric-value">{metrics['aggregate_metrics']['max_confidence']:.3f}</span>
            </div>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>Sequence Name</th>
                    <th>Frames in Video</th>
                    <th>Frames Sampled</th>
                    <th>Avg Confidence</th>
                    <th>Classes Detected</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # Add sequence metrics
    for seq_name, seq_metrics in metrics['sequence_metrics'].items():
        html_content += f"""
                <tr>
                    <td><strong>{seq_name}</strong></td>
                    <td>{seq_metrics['frames_in_video']}</td>
                    <td>{seq_metrics['frames_sampled']}</td>
                    <td>{seq_metrics['avg_confidence']:.3f}</td>
                    <td>{seq_metrics['classes_detected']}</td>
                </tr>
"""
    
    html_content += """
            </tbody>
        </table>
        
        <div class="gallery">
            <h2>🖼️ Segmentation Results</h2>
"""
    
    # Add sample images
    for seq_name in sorted(sample_images.keys()):
        html_content += f'<div class="sequence-gallery">\n'
        html_content += f'<div class="sequence-title">{seq_name}</div>\n'
        html_content += '<div class="image-grid">\n'
        
        for img_file in sample_images[seq_name]:
            img_path = os.path.join(FRAMES_DIR, seq_name, img_file)
            if os.path.exists(img_path):
                # Convert to relative path for HTML
                rel_path = os.path.relpath(img_path, REPORT_DIR)
                label = img_file.replace('_', ' ').replace('.png', '').title()
                html_content += f"""
        <div class="image-container">
            <img src="{rel_path}" alt="{label}">
            <div class="image-label">{label}</div>
        </div>
"""
        
        html_content += '</div>\n</div>\n'
    
    html_content += """
        </div>
        
        <footer>
            <p>Video Object Segmentation using DeepLabV3 (ResNet50 backbone, Pascal VOC pretrained)</p>
            <p>DAVIS Dataset: Unsupervised Video Object Segmentation Benchmark</p>
        </footer>
    </div>
</body>
</html>
"""
    
    report_path = os.path.join(REPORT_DIR, 'index.html')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    logger.info(f"✓ HTML report generated: {report_path}")
    return report_path


if __name__ == '__main__':
    print("\n" + "="*70)
    print("DAVIS VOS Analysis - Generating Reports")
    print("="*70 + "\n")
    
    report_path = create_html_report()
    
    print("\n" + "="*70)
    print("REPORTS GENERATED")
    print("="*70)
    print(f"✓ HTML Report: {os.path.abspath(report_path)}")
    print(f"✓ Metrics Report: {os.path.abspath(os.path.join(REPORT_DIR, 'metrics_report.json'))}")
    print("="*70 + "\n")
