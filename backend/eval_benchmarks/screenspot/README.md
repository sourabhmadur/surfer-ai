# ScreenSpot Evaluation

This directory contains the implementation for evaluating models on the ScreenSpot dataset, which tests the ability to locate UI elements in screenshots based on natural language instructions.

## Dataset Structure

- `screenspot_web.json`: Contains the dataset annotations with the following fields:
  - `img_filename`: Name of the screenshot image file
  - `bbox`: Bounding box coordinates [x, y, width, height]
  - `instruction`: Natural language instruction describing the UI element to find
  - `data_type`: Type of UI element (text, icon)
  - `data_source`: Source website/application

- `images/`: Directory containing the screenshot images referenced in the dataset

## Setup

1. Install the required dependencies:
```bash
pip install -r requirements.txt
```

2. Place the ScreenSpot dataset images in the `images/` directory

## Running the Evaluation

### Quick Test
To run a quick test of the evaluation code:
```bash
python test_screenspot.py
```

This will evaluate a few example predictions against the ground truth.

### Full Evaluation
To evaluate your model on the dataset:
```bash
python run_eval.py
```

By default, this will evaluate on 10 samples. To evaluate on more samples, modify the `num_samples` parameter in `run_eval.py`.

## Evaluation Metrics

The evaluation computes the following metrics:
- **Accuracy**: Percentage of predictions with IoU ≥ 0.5
- **Mean IoU**: Average Intersection over Union across all predictions
- **Total Evaluated**: Number of samples successfully evaluated

## Implementation Details

### ScreenSpotEvaluator
The main evaluation class that:
- Loads the dataset and images
- Computes IoU between predicted and ground truth bounding boxes
- Evaluates predictions against ground truth
- Computes evaluation metrics

### ScreenSpotRunner
The runner class that:
- Communicates with your model via WebSocket
- Processes images and instructions
- Collects predictions
- Runs the evaluation

## Customization

To use your own model:
1. Modify the `get_model_prediction()` method in `ScreenSpotRunner` to communicate with your model
2. Update the WebSocket endpoint in the `ScreenSpotRunner` initialization
3. Adjust the prediction format to match your model's output

## Notes

- The evaluation uses an IoU threshold of 0.5 by default
- Images are expected to be in PNG format
- The WebSocket communication is currently stubbed out and needs to be implemented 