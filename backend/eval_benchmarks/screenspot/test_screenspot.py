import unittest
from unittest.mock import patch, mock_open
import os
import json
from screenspot_eval import ScreenSpotEvaluator

class TestScreenSpotEvaluator(unittest.TestCase):
    def setUp(self):
        """Set up test environment."""
        self.test_dir = os.path.dirname(os.path.abspath(__file__))
        self.evaluator = ScreenSpotEvaluator(
            data_path=os.path.join(self.test_dir, "screenspot_web.json"),
            images_dir=os.path.join(self.test_dir, "screenspot_imgs")
        )
        
        # Mock dataset for testing
        self.mock_dataset = [
            {
                "img_filename": "test1.png",
                "instruction": "Click the submit button",
                "bbox": [100, 100, 50, 30]  # x, y, width, height
            },
            {
                "img_filename": "test2.png",
                "instruction": "Click the menu icon",
                "bbox": [20, 20, 40, 40]  # x, y, width, height
            }
        ]
            
    def test_point_in_bbox(self):
        """Test point in bounding box detection."""
        # Test point inside bbox
        self.assertTrue(self.evaluator.is_point_in_bbox(120, 110, [100, 100, 50, 30]))
        
        # Test point on bbox edge
        self.assertTrue(self.evaluator.is_point_in_bbox(100, 100, [100, 100, 50, 30]))
        self.assertTrue(self.evaluator.is_point_in_bbox(150, 130, [100, 100, 50, 30]))
        
        # Test point outside bbox
        self.assertFalse(self.evaluator.is_point_in_bbox(99, 100, [100, 100, 50, 30]))
        self.assertFalse(self.evaluator.is_point_in_bbox(151, 110, [100, 100, 50, 30]))
        self.assertFalse(self.evaluator.is_point_in_bbox(120, 131, [100, 100, 50, 30]))
        
    def test_evaluate_prediction(self):
        """Test evaluation of a single prediction."""
        # Test correct prediction (point inside bbox)
        prediction = {
            'img_filename': 'test1.png',
            'instruction': 'Click the submit button',
            'coordinates': {'x': 120, 'y': 110}
        }
        ground_truth = self.mock_dataset[0]
        result = self.evaluator.evaluate_prediction(prediction, ground_truth)
        self.assertTrue(result['is_correct'])
        
        # Test incorrect prediction (point outside bbox)
        prediction = {
            'img_filename': 'test1.png',
            'instruction': 'Click the submit button',
            'coordinates': {'x': 90, 'y': 110}
        }
        result = self.evaluator.evaluate_prediction(prediction, ground_truth)
        self.assertFalse(result['is_correct'])
        
        # Test distance calculation to center
        prediction = {
            'img_filename': 'test1.png',
            'instruction': 'Click the submit button',
            'coordinates': {'x': 125, 'y': 115}  # Center of bbox is at (125, 115)
        }
        result = self.evaluator.evaluate_prediction(prediction, ground_truth)
        self.assertEqual(result['distance'], 0.0)  # Should be 0 at center
        
    def test_evaluate_batch(self):
        """Test batch evaluation with mock data."""
        # Mock predictions
        predictions = [
            {
                'img_filename': 'test1.png',
                'instruction': 'Click the submit button',
                'coordinates': {'x': 125, 'y': 115}  # Inside first bbox
            },
            {
                'img_filename': 'test2.png',
                'instruction': 'Click the menu icon',
                'coordinates': {'x': 10, 'y': 10}  # Outside second bbox
            }
        ]
        
        # Mock the file open operation
        mock_file_content = json.dumps(self.mock_dataset)
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            results = self.evaluator.evaluate_batch(predictions)
            
            self.assertEqual(results['total_evaluated'], 2)
            self.assertEqual(results['accuracy'], 0.5)  # 1 out of 2 correct
            self.assertGreater(results['mean_distance'], 0)  # Should be non-zero due to second prediction
        
    def test_empty_batch(self):
        """Test evaluation with empty batch."""
        # Mock the file open operation
        mock_file_content = json.dumps(self.mock_dataset)
        with patch('builtins.open', mock_open(read_data=mock_file_content)):
            results = self.evaluator.evaluate_batch([])
            self.assertEqual(results['accuracy'], 0.0)
            self.assertEqual(results['mean_distance'], float('inf'))
            self.assertEqual(results['total_evaluated'], 0)

if __name__ == '__main__':
    unittest.main() 