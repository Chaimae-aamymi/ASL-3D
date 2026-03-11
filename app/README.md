# Degradation Detector - ASL-3D

Professional building degradation detection system using Deep Learning (CNN).

## Features

- Detection: Identify 6 types of building degradations
- Analysis: Classification + Semantic Segmentation
- Localization: Precise location of affected areas
- Export: Save analysis results

## Degradation Types

- Fissures (Cracks)
- Humidité (Humidity)
- Érosion (Erosion)
- Champignons (Fungi)
- Décoloration (Discoloration)
- Effritement (Crumbling)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```python
from degradation_detector import DegradationDetector
detector = DegradationDetector()
degradations = detector.detect(image_array)
```

## Model Architecture

- **Classification**: MobileNetV2 + Custom Layers (Transfer Learning)
- **Segmentation**: U-Net (256x256)
- **Framework**: TensorFlow/Keras

## License

MIT
