import os
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
import math

def process_image(input_path: str, output_dir: str, grid_spacing: int = 50, tile_size: int = 784):
    """Process an image by adding axes and grid lines.
    
    Args:
        input_path: Path to input image
        output_dir: Directory to save processed images
        grid_spacing: Spacing between grid lines in pixels
        tile_size: Size of tiles to generate
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Load image
    img = Image.open(input_path)
    img_array = np.array(img)
    
    def add_grid_and_save(img_array, output_path, x_offset=0, y_offset=0):
        """Add grid lines and save image."""
        # Create figure and axis
        plt.figure(figsize=(img_array.shape[1]/100, img_array.shape[0]/100), dpi=100)
        ax = plt.gca()
        
        # Display image
        ax.imshow(img_array)
        
        # Add grid lines and labels
        x_ticks = np.arange(0, img_array.shape[1], grid_spacing)
        y_ticks = np.arange(0, img_array.shape[0], grid_spacing)
        
        # Add grid lines
        ax.set_xticks(x_ticks)
        ax.set_yticks(y_ticks)
        ax.grid(True, color='gray', alpha=0.5, linewidth=0.5)
        
        # Set tick labels to show absolute coordinates
        ax.set_xticklabels([int(x + x_offset) for x in x_ticks], rotation=45, ha='right')
        ax.set_yticklabels([int(y + y_offset) for y in y_ticks], rotation=45, ha='right')
        
        # Add background to tick labels for better visibility
        for tick in ax.get_xticklabels():
            tick.set_bbox(dict(facecolor='white', edgecolor='none', alpha=0.7))
        for tick in ax.get_yticklabels():
            tick.set_bbox(dict(facecolor='white', edgecolor='none', alpha=0.7))
        
        # Remove axis padding
        plt.margins(0)
        plt.subplots_adjust(left=0, right=1, bottom=0, top=1)
        
        # Save image
        plt.savefig(output_path, bbox_inches='tight', pad_inches=0)
        plt.close()
    
    # Save original image with axes
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}.png")
    add_grid_and_save(img_array, output_path)
    print(f"Saved original image with grid: {output_path}")
    
    # Calculate number of tiles needed
    height, width = img_array.shape[:2]
    num_tiles_y = math.ceil(height / tile_size)
    num_tiles_x = math.ceil(width / tile_size)
    print(f"Generating {num_tiles_x * num_tiles_y} tiles ({num_tiles_x}x{num_tiles_y})")
    
    # Generate tiles
    for i in range(num_tiles_y):
        for j in range(num_tiles_x):
            # Calculate tile coordinates
            left = j * tile_size
            top = i * tile_size
            right = min((j + 1) * tile_size, width)
            bottom = min((i + 1) * tile_size, height)
            
            # Extract tile
            tile_array = img_array[top:bottom, left:right]
            
            # Save tile with grid and absolute coordinates
            tile_path = os.path.join(output_dir, f"{base_name}_{i * num_tiles_x + j + 1}.png")
            add_grid_and_save(tile_array, tile_path, x_offset=left, y_offset=top)
            print(f"Saved tile {i * num_tiles_x + j + 1} at position ({left}, {top})")

def process_directory(input_dir: str, output_dir: str, grid_spacing: int = 50, tile_size: int = 784):
    """Process all images in a directory.
    
    Args:
        input_dir: Directory containing input images
        output_dir: Directory to save processed images
        grid_spacing: Spacing between grid lines in pixels
        tile_size: Size of tiles to generate
    """
    # Check if input directory exists
    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    print(f"Processing images from {input_dir}")
    print(f"Saving results to {output_dir}")
    
    # Get list of image files
    image_files = [f for f in os.listdir(input_dir) 
                  if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    if not image_files:
        print(f"No image files found in {input_dir}")
        return
    
    print(f"Found {len(image_files)} images to process")
    
    # Process each image in input directory
    for i, filename in enumerate(image_files, 1):
        try:
            input_path = os.path.join(input_dir, filename)
            print(f"\nProcessing image {i}/{len(image_files)}: {filename}")
            process_image(input_path, output_dir, grid_spacing, tile_size)
            print(f"Successfully processed {filename}")
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")
            continue

if __name__ == "__main__":
    try:
        # Get the parent directory (screenspot)
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Example usage
        input_dir = os.path.join(current_dir, "screenspot_images/screenspot_imgs")
        output_dir = os.path.join(current_dir, "screenspot_images/screenspot_imgs_axes")
        
        print(f"Input directory: {input_dir}")
        print(f"Output directory: {output_dir}")
        
        process_directory(input_dir, output_dir)
        print("\nProcessing complete!")
    except Exception as e:
        print(f"\nError: {str(e)}")
        import traceback
        print(traceback.format_exc()) 