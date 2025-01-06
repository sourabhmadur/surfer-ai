import os
import json
from typing import Dict, List
import math
class ScreenSpotEvaluator:
    def __init__(self, data_path: str, images_dir: str):
        """Initialize the ScreenSpot evaluator.
        
        Args:
            data_path: Path to the dataset JSON file
            images_dir: Path to the directory containing images
        """
        self.data_path = data_path
        self.images_dir = images_dir
        
    def is_point_in_bbox(self, x: int, y: int, bbox: List[int]) -> bool:
        """Check if a point (x,y) falls within a bounding box.
        
        Args:
            x: X coordinate of the point
            y: Y coordinate of the point
            bbox: Bounding box in format [left, top, width, height]
            
        Returns:
            True if point is inside bbox, False otherwise
        """
        # Unpack bbox parameters
        left, top, width, height = bbox
        print(f"Checking point ({x}, {y}) against bbox: left={left}, top={top}, width={width}, height={height}")
        
        # Check if point is inside bbox
        is_inside = (left <= x <= left + width) and (top <= y <= top + height)
        if is_inside:
            print(f"Point ({x}, {y}) is inside bbox [{left}:{left+width}, {top}:{top+height}]")
        else:
            print(f"Point ({x}, {y}) is outside bbox [{left}:{left+width}, {top}:{top+height}]")
        return is_inside
    
    def evaluate_prediction(self, prediction: Dict, ground_truth: Dict) -> Dict:
        """Evaluate a single prediction against ground truth.
        
        Args:
            prediction: Dictionary containing predicted coordinates
            ground_truth: Dictionary containing ground truth bbox
            
        Returns:
            Dictionary with evaluation metrics
        """
        pred_coords = prediction['coordinates']
        gt_bbox = ground_truth['bbox']
        
        # Check if predicted coordinates fall within ground truth bbox
        is_correct = self.is_point_in_bbox(
            pred_coords['x'], 
            pred_coords['y'], 
            gt_bbox
        )
        
        # Calculate center point of bbox for distance calculation
        bbox_center_x = (gt_bbox[0] + (gt_bbox[0] + gt_bbox[2])) / 2
        bbox_center_y = (gt_bbox[1] + (gt_bbox[1] + gt_bbox[3])) / 2
        
        # Calculate distance to bbox center
        distance = math.sqrt((pred_coords['x'] - bbox_center_x) ** 2 + 
                   (pred_coords['y'] - bbox_center_y) ** 2)
        
        return {
            'distance': distance,
            'is_correct': is_correct
        }
        
    def evaluate_batch(self, predictions: List[Dict]) -> Dict:
        """Evaluate a batch of predictions.
        
        Args:
            predictions: List of dictionaries containing predictions
            
        Returns:
            Dictionary with evaluation metrics
        """
        # Load ground truth data
        with open(self.data_path, 'r') as f:
            dataset = json.load(f)
            
        # Create lookup for ground truth by image filename AND instruction
        gt_lookup = {(item['img_filename'], item['instruction']): item for item in dataset}
        
        total_correct = 0
        total_distance = 0
        total_evaluated = 0
        
        for pred in predictions:
            key = (pred['img_filename'], pred['instruction'])
            if key not in gt_lookup:
                print(f"No ground truth found for {key}")
                continue
                
            gt = gt_lookup[key]
            print(f"\nEvaluating prediction for {key}:")
            print(f"Ground truth bbox: {gt['bbox']}")
            print(f"Predicted coordinates: {pred['coordinates']}")
            
            result = self.evaluate_prediction(pred, gt)
            
            total_correct += int(result['is_correct'])
            total_distance += result['distance']
            total_evaluated += 1
            
        if total_evaluated == 0:
            return {
                'accuracy': 0.0,
                'mean_distance': float('inf'),
                'total_evaluated': 0
            }
            
        return {
            'accuracy': total_correct / total_evaluated,
            'mean_distance': total_distance / total_evaluated,
            'total_evaluated': total_evaluated
        } 