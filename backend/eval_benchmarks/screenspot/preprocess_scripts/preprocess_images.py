import os
from PIL import Image, ImageDraw, ImageFont
from typing import Optional, Tuple
import argparse

def add_grid_to_image(img: Image, grid_size: int = 100) -> Image:
    """Add a Cartesian coordinate grid overlay to an image.
    
    Args:
        img: PIL Image to add grid to
        grid_size: Size of grid cells in pixels (default: 100 pixels)
        
    Returns:
        PIL Image with coordinate grid overlay
    """
    # Create a copy of the image
    img_copy = img.copy()
    
    # Convert to RGB if needed
    if img_copy.mode != 'RGB':
        img_copy = img_copy.convert('RGB')
    
    width, height = img_copy.size
    print(f"Original dimensions: {width}x{height}")
    
    # Create a drawing object
    draw = ImageDraw.Draw(img_copy)
    
    # Try to load a system font, fallback to default if not found
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 14)
    except:
        font = ImageFont.load_default()
    
    def draw_text_with_background(draw, pos, text, font, text_color='black', bg_color='white', opacity=180):
        """Draw text with a background box for better readability."""
        # Get text size
        bbox = draw.textbbox(pos, text, font=font)
        # Add padding
        padding = 2
        background_bbox = (
            bbox[0] - padding,
            bbox[1] - padding,
            bbox[2] + padding,
            bbox[3] + padding
        )
        
        # Draw white background rectangle
        draw.rectangle(background_bbox, fill='white')
        
        # Draw text
        draw.text(pos, text, fill=text_color, font=font)
    
    # Draw dotted grid lines and labels
    for x in range(0, width, grid_size):
        # Draw dotted vertical lines
        for y in range(0, height, 6):  # 4 pixels on, 2 pixels off
            draw.line([(x, y), (x, min(y+4, height))], fill='yellow', width=1)
        # Add x-coordinate label at bottom
        draw_text_with_background(draw, (x - 10, height - 20), str(x), font)
    
    for y in range(0, height, grid_size):
        # Draw dotted horizontal lines
        for x in range(0, width, 6):  # 4 pixels on, 2 pixels off
            draw.line([(x, y), (min(x+4, width), y)], fill='yellow', width=1)
        # Add y-coordinate label on left
        draw_text_with_background(draw, (5, y - 8), str(y), font)
    
    return img_copy

def preprocess_images(input_dir: str, output_dir: str, grid_size: int = 100, resize_dims: Optional[Tuple[int, int]] = None):
    """Process all images in a directory, adding grid lines and optionally resizing.
    
    Args:
        input_dir: Directory containing input images
        output_dir: Directory to save processed images
        grid_size: Size of grid cells in pixels
        resize_dims: Optional tuple of (width, height) to resize images
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each image in input directory
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            
            print(f"\nProcessing {filename}...")
            
            try:
                with Image.open(input_path) as img:
                    # First add grid lines
                    processed_img = add_grid_to_image(img, grid_size)
                    
                    # Then resize if dimensions provided
                    if resize_dims:
                        processed_img = processed_img.resize(resize_dims, Image.Resampling.LANCZOS)
                        print(f"Resized to: {resize_dims[0]}x{resize_dims[1]}")
                    
                    # Save with high quality
                    processed_img.save(output_path, quality=95)
                    print(f"Saved to {output_path}")
            except Exception as e:
                print(f"Error processing {filename}: {str(e)}")

def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Preprocess images by adding grid lines')
    parser.add_argument('--input-dir', type=str, default='screenspot_images/screenspot_imgs',
                        help='Directory containing input images')
    parser.add_argument('--output-dir', type=str, default='screenspot_images/screenspot_imgs_grid',
                        help='Directory to save processed images')
    parser.add_argument('--grid-spacing', type=int, default=100,
                        help='Spacing between grid lines in pixels')
    parser.add_argument('--tile-size', type=int, default=784,
                        help='Size of tiles to generate')
    args = parser.parse_args()
    
    try:
        # Get the parent directory (screenspot)
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Set up input and output directories
        input_dir = os.path.join(current_dir, args.input_dir)
        output_dir = os.path.join(current_dir, args.output_dir)
        resize_output_dir = os.path.join(current_dir, 'screenspot_images/screenspot_imgs_grid_resize')
        
        if args.resize:
            resize_dims = (1440, 990)
        else:
            resize_dims = None
        
        preprocess_images(input_dir, output_dir, args.grid_size, resize_dims)
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main() 