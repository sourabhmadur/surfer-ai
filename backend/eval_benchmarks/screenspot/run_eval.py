import os
import json
import asyncio
from typing import Dict, List, Tuple
from PIL import Image
import base64
import io
from screenspot_eval import ScreenSpotEvaluator
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import re
from datetime import datetime
import math

# Load environment variables
load_dotenv()

# Create runs directory if it doesn't exist
current_dir = os.path.dirname(os.path.abspath(__file__))
runs_dir = os.path.join(current_dir, "runs")
os.makedirs(runs_dir, exist_ok=True)

VISUAL_ELEMENT_PROMPT = '''Given the screenshot and the instruction, identify the exact element to click on and return its CENTER coordinates.
Focus on finding the most relevant element that matches the instruction.

The image has a grid overlay with lines every 100 pixels to help you determine coordinates of the elements center:
1. Each vertical grid line shows its X coordinate (0, 100, 200, ...)
2. Each horizontal grid line shows its Y coordinate (0, 100, 200, ...)
3. Use grid lines as reference points to determine exact coordinates
4. For elements between grid lines, estimate the position (e.g., if an element is 3/4 of the way between 2300 and 2400, its x-coordinate would be 2375)

{tile_info}

Analyze the visual characteristics:
1. First locate the element relative to nearby grid lines
2. Use grid coordinates to determine the exact position
3. Pay attention to text content, colors, and styles
4. Consider the semantic meaning of the instruction
5. When using tiles, specify which tiles you used to determine the coordinates

IMPORTANT: You must respond with ONLY a valid JSON object in this exact format:
{{
    "element_data": {{
        "coordinates": {{
            "x": integer,  # X coordinate determined using grid lines as reference
            "y": integer   # Y coordinate determined using grid lines as reference
        }},
        "element_description": "Detailed description including grid line references",
        "confidence": float,  # Between 0 and 1
        "tiles_used": [integer],  # List of tile numbers used to determine coordinates (e.g., [1, 2] for tiles 1 and 2). Use [] if no tiles were used.
        "tile_explanation": "Brief explanation of how the tiles were used to determine coordinates"
    }}
}}

Do not include any other text, markdown formatting, or explanations outside the JSON object.

Guidelines for finding coordinates using grid lines:
1. First identify which grid cell contains your target element
2. Note the coordinates of the surrounding grid lines
3. For text elements: Find middle point between grid lines containing the text
4. For buttons: Use grid lines to measure button edges and find center
5. For inputs: Use grid lines to find the center of the input field
6. For links: Use grid lines to find the middle point of the link text
7. For images: Use grid lines to find the center point of the image
8. For icons: Use grid lines to find the center point of the icon
9. If element spans multiple grid cells, find the center point
10. X increases left to right (count grid lines from left edge)
11. Y increases top to bottom (count grid lines from top edge)

Example Response (ONLY return a JSON object like this, with no other text):
{{
    "element_data": {{
        "coordinates": {{
            "x": 2425,
            "y": 48
        }},
        "element_description": "Blue 'Settings' button located between grid lines 2400 and 2500 horizontally, and between grid lines 0 and 100 vertically. The button's center is approximately at coordinates (2425, 48)",
        "confidence": 0.95,
        "tiles_used": [1, 2],
        "tile_explanation": "Used tile 1 to identify the button's left edge and tile 2 to confirm its right edge and text content"
    }}
}}'''

def get_image_tiles(base_name: str, images_dir: str) -> Tuple[str, List[str]]:
    """Get original image and all tile images for a given base name.
    
    Args:
        base_name: Base name of the image without extension
        images_dir: Directory containing the images and tiles
        
    Returns:
        Tuple of (original_image_path, list of tile paths)
    """
    tiles = []
    original_path = os.path.join(images_dir, f"{base_name}.png")
    
    # Look for files matching pattern: base_name_1.png, base_name_2.png, etc.
    for file in os.listdir(images_dir):
        if file.startswith(base_name + "_") and file.endswith(".png"):
            try:
                # Extract tile number from filename
                tile_num = int(file.split("_")[-1].split(".")[0])
                tile_path = os.path.join(images_dir, file)
                tiles.append((tile_path, tile_num))
            except ValueError:
                continue
    
    # Sort by tile number
    tiles.sort(key=lambda x: x[1])
    return original_path, [t[0] for t in tiles]  # Return original path and sorted tile paths

class ScreenSpotRunner:
    def __init__(self, use_tiles: bool = False):
        """Initialize the ScreenSpot evaluation runner.
        
        Args:
            use_tiles: Whether to use pre-generated tiles
        """
        # Initialize Gemini model
        self.model = ChatGoogleGenerativeAI(
            model=MODEL,
            convert_system_message_to_human=True
        )
        self.use_tiles = use_tiles
        
    def _image_to_base64(self, image_path: str) -> str:
        """Convert image file to base64 string."""
        with open(image_path, 'rb') as f:
            return base64.b64encode(f.read()).decode()
        
    async def get_model_prediction(self, image_path: str, instruction: str) -> Dict:
        """Get prediction from the Gemini model."""
        print("\n[DEBUG] Starting get_model_prediction...", flush=True)
        print(f"[DEBUG] Processing image: {image_path}", flush=True)
        print(f"[DEBUG] Instruction: {instruction}", flush=True)
        
        # Get base name without extension
        base_name = os.path.splitext(os.path.basename(image_path))[0]
        images_dir = os.path.dirname(image_path)
        print(f"[DEBUG] Base name: {base_name}", flush=True)
        print(f"[DEBUG] Images dir: {images_dir}", flush=True)
        
        # Prepare content for prompt
        content = []
        
        if self.use_tiles:
            print("[DEBUG] Using tiles mode", flush=True)
            # Get original image and tile images
            _, tile_paths = get_image_tiles(base_name, images_dir)
            print(f"[DEBUG] Found {len(tile_paths)} tiles", flush=True)
            
            if tile_paths:
                print("[DEBUG] Processing tiles...", flush=True)
                # Prepare tile info
                tile_info = "Below are detailed tiles of the image for better visibility. Each tile shows its absolute position in the original image."
                
                # Add the prompt with tile info
                content.append({
                    "type": "text",
                    "text": VISUAL_ELEMENT_PROMPT.format(tile_info=tile_info)
                })
                
                # Add the instruction
                content.append({
                    "type": "text",
                    "text": f"Instruction: {instruction}"
                })
                
                # Add original image first
                content.append({
                    "type": "text",
                    "text": "Original full image:"
                })
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{self._image_to_base64(image_path)}"}
                })
                
                # Add tiles
                for i, tile_path in enumerate(tile_paths, 1):
                    print(f"[DEBUG] Processing tile {i}: {tile_path}", flush=True)
                    img_uri = f"data:image/png;base64,{self._image_to_base64(tile_path)}"
                    content.append({
                        "type": "text",
                        "text": f"Tile {i}"
                    })
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": img_uri}
                    })
            else:
                print("[DEBUG] No tiles found, using original image only", flush=True)
                tile_info = "The image is shown in its original size with grid overlay."
                print(f"[DEBUG] Using original image: {image_path}", flush=True)
                content.extend([
                    {"type": "text", "text": VISUAL_ELEMENT_PROMPT.format(tile_info=tile_info)},
                    {"type": "text", "text": f"Instruction: {instruction}"},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{self._image_to_base64(image_path)}"}}
                ])
        else:
            print("[DEBUG] Using full image mode with grid overlay", flush=True)
            tile_info = "The image is shown in its original size with grid overlay."
            content.extend([
                {"type": "text", "text": VISUAL_ELEMENT_PROMPT.format(tile_info=tile_info)},
                {"type": "text", "text": f"Instruction: {instruction}"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{self._image_to_base64(image_path)}"}}
            ])
        
        # Get Gemini response
        messages = [{"role": "user", "content": content}]
        print("\n[DEBUG] Sending request to Gemini model...", flush=True)
        print("[DEBUG] Content structure:", flush=True)
        for i, item in enumerate(content):
            print(f"Item {i} type: {item['type']}", flush=True)
        
        try:
            response = self.model.invoke(messages)
            print("\n[DEBUG] Received response from model", flush=True)
            print(f"[DEBUG] Response type: {type(response)}", flush=True)
            print(f"[DEBUG] Response content type: {type(response.content)}", flush=True)
            print(f"[DEBUG] Raw response content: {repr(response.content)}", flush=True)
            
            if not response or not hasattr(response, 'content'):
                raise ValueError("Empty or invalid response from model")
                
            # Parse JSON response
            content = response.content
            if not content:
                raise ValueError("Empty content in model response")
                
            print(f"\n[DEBUG] Initial content: {repr(content)}", flush=True)
            
            if isinstance(content, list):
                content = ' '.join(content)
                print(f"[DEBUG] After joining list: {repr(content)}", flush=True)
            
            # Clean up the response text
            content = content.strip()
            print(f"[DEBUG] After strip: {repr(content)}", flush=True)
            
            if not content:
                raise ValueError("Content is empty after cleanup")
            
            # Remove any leading/trailing whitespace or quotes
            content = content.strip('"\'')
            print(f"[DEBUG] After quote strip: {repr(content)}", flush=True)
            
            # If response starts with a newline and JSON structure, clean it up
            if content.startswith('\n'):
                content = content.lstrip()
                print(f"[DEBUG] After lstrip: {repr(content)}", flush=True)
            
            # Extract JSON if wrapped in code block
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
                print(f"[DEBUG] After code block extraction: {repr(content)}", flush=True)
            
            # Try to parse the JSON
            try:
                print(f"[DEBUG] Attempting to parse JSON: {repr(content)}", flush=True)
                # If content is just "element_data", wrap it in braces
                if content.strip() == '"element_data"':
                    raise ValueError("Response contains only 'element_data' string")
                    
                data = json.loads(content)
                print(f"[DEBUG] Successfully parsed JSON: {json.dumps(data, indent=2)}", flush=True)
            except json.JSONDecodeError as je:
                print(f"[DEBUG] First JSON parse failed: {str(je)}", flush=True)
                # If direct parsing fails, try to clean up the string more aggressively
                content = re.sub(r'^[^{]*({.*})[^}]*$', r'\1', content, flags=re.DOTALL)
                print(f"[DEBUG] After aggressive cleanup: {repr(content)}", flush=True)
                data = json.loads(content)
                print(f"[DEBUG] Successfully parsed JSON after cleanup: {json.dumps(data, indent=2)}", flush=True)
            
            if not isinstance(data, dict) or "element_data" not in data:
                raise ValueError(f"Invalid response format. Expected dict with 'element_data' key. Got: {type(data)}")
            
            result = {
                "coordinates": data["element_data"]["coordinates"],
                "description": data["element_data"]["element_description"],
                "confidence": data["element_data"]["confidence"],
                "tiles_used": data["element_data"].get("tiles_used", []),
                "tile_explanation": data["element_data"].get("tile_explanation", "No tile explanation provided")
            }
            print(f"[DEBUG] Final result: {json.dumps(result, indent=2)}", flush=True)
            return result
            
        except Exception as e:
            print(f"\n[DEBUG] Exception occurred!", flush=True)
            print(f"[DEBUG] Exception type: {type(e)}", flush=True)
            print(f"[DEBUG] Exception message: {str(e)}", flush=True)
            if 'response' in locals():
                print(f"[DEBUG] Raw response content: {repr(response.content)}", flush=True)
            else:
                print("[DEBUG] No response object available", flush=True)
            raise Exception(f"Failed to parse model response: {str(e)}")
        
    def _is_point_in_bbox(self, x: int, y: int, bbox: List) -> bool:
        """Check if point (x,y) is within the bounding box.
        
        Args:
            x: x-coordinate to check
            y: y-coordinate to check
            bbox: List of [x, y, width, height]
            
        Returns:
            bool: True if point is within bbox
        """
        bbox_x, bbox_y, bbox_width, bbox_height = bbox
        return (bbox_x <= x <= bbox_x + bbox_width and 
                bbox_y <= y <= bbox_y + bbox_height)

    async def run_evaluation(self, num_samples: int = None, run_name: str = "gemini_run") -> Dict:
        """Run evaluation on the ScreenSpot dataset."""
        print("\n[DEBUG] Starting evaluation...", flush=True)
        
        # Initialize evaluator
        evaluator = ScreenSpotEvaluator(
            data_path=os.path.join(current_dir, "screenspot_web.json"),
            images_dir=os.path.join(current_dir, IMGS_DIR)
        )
        print(f"[DEBUG] Initialized evaluator with data path: {evaluator.data_path}", flush=True)
        print(f"[DEBUG] Images directory: {evaluator.images_dir}", flush=True)
        
        # Load dataset
        with open(evaluator.data_path, 'r') as f:
            dataset = json.load(f)
        print(f"[DEBUG] Loaded dataset with {len(dataset)} samples", flush=True)
            
        if num_samples:
            dataset = dataset[:num_samples]
            print(f"[DEBUG] Using {num_samples} samples for evaluation", flush=True)
            
        # Get predictions for each sample
        predictions = []
        for i, item in enumerate(dataset):
            print(f"\n[DEBUG] Processing sample {i+1}/{len(dataset)}...", flush=True)
            print(f"[DEBUG] Image: {item['img_filename']}", flush=True)
            print(f"[DEBUG] Instruction: {item['instruction']}", flush=True)
            
            img_path = os.path.join(evaluator.images_dir, item['img_filename'])
            if not os.path.exists(img_path):
                print(f"[DEBUG] Warning: Image not found: {img_path}", flush=True)
                continue
                
            try:
                pred = await self.get_model_prediction(img_path, item['instruction'])
                print(f"[DEBUG] Got prediction: {json.dumps(pred, indent=2)}", flush=True)
                
                # Check if predicted coordinates are in bounding box
                is_in_bbox = self._is_point_in_bbox(
                    pred['coordinates']['x'],
                    pred['coordinates']['y'],
                    item['bbox']
                )
                print(f"[DEBUG] Prediction in bounding box: {is_in_bbox}", flush=True)
                
                predictions.append({
                    'img_filename': item['img_filename'],
                    'gt': item,
                    'instruction': item['instruction'],
                    'coordinates': pred['coordinates'],
                    'description': pred['description'],
                    'confidence': pred['confidence'],
                    'is_in_bbox': is_in_bbox,
                    'tiles_used': pred['tiles_used'],
                    'tile_explanation': pred['tile_explanation']
                })
            except Exception as e:
                print(f"[DEBUG] Error processing {item['img_filename']}: {str(e)}", flush=True)
                print(f"[DEBUG] Exception type: {type(e)}", flush=True)
                print(f"[DEBUG] Exception traceback:", flush=True)
                import traceback
                print(traceback.format_exc(), flush=True)
        
        # Save predictions to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        predictions_file = os.path.join(runs_dir, f"{timestamp}_{run_name}.json")
        
        print("\n[DEBUG] Starting evaluation of predictions...", flush=True)
        results = evaluator.evaluate_batch(predictions)
        print(f"[DEBUG] Evaluation complete: {json.dumps(results, indent=2)}", flush=True)
        
        # Save both predictions and results
        with open(predictions_file, 'w') as f:
            json.dump({
                'timestamp': timestamp,
                'run_name': run_name,
                'num_samples': num_samples,
                'use_tiles': self.use_tiles,
                'predictions': predictions,
                'results': {
                    'accuracy': results['accuracy'],
                    'mean_distance': results['mean_distance'],
                    'total_evaluated': results['total_evaluated']
                }
            }, f, indent=2)
        print(f"\n[DEBUG] Saved predictions and results to: {predictions_file}", flush=True)
        
        return results

async def main():
    runner = ScreenSpotRunner(use_tiles=USE_TILES)
    results = await runner.run_evaluation(
        num_samples=NUM_SAMPLES,
        run_name=RUN_NAME
    )
    
    print("\nEvaluation Results:")
    print(f"Accuracy: {results['accuracy']:.3f}")
    print(f"Mean Distance: {results['mean_distance']:.3f}")
    print(f"Total Evaluated: {results['total_evaluated']}")


NUM_SAMPLES = 10
MODEL = "gemini-2.0-flash-thinking-exp-1219"
USE_TILES = False  # Set to True to use tiled images
IMGS_DIR = "screenspot_imgs_axes"  # Directory with grid-overlayed images
RUN_NAME = MODEL + "_" + ("tiles" if USE_TILES else "full") + "_" + str(NUM_SAMPLES)

if __name__ == "__main__":
    asyncio.run(main()) 