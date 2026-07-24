import os
import logging
from typing import List, Dict
import pollinations as ai
import config

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def create_from_data(data: List[Dict[str, str]], output_dir: str) -> None:
    """Iterate through parsed scene data and generate background images.
    
    Args:
        data: List of scene elements parsed from the script.
        output_dir: Directory where generated images will be saved.
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    image_number = 0
    for element in data:
        if element["type"] != "image":
            continue
        
        image_name = f"image_{image_number}.jpg"
        prompt = element["description"] + ". Vertical image, fully filling the canvas."
        output_file = os.path.join(output_dir, image_name)
        
        logger.info("Generating image %d: %s", image_number, element["description"])
        generate(
            prompt=prompt, 
            output_file=output_file,
            width=config.DEFAULT_WIDTH * 2, # Using double size (e.g. 1152x2048) for high resolution generation
            height=config.DEFAULT_HEIGHT * 2,
            seed=42 + image_number
        )
        image_number += 1

def generate(prompt: str, output_file: str, width: int = 1080, height: int = 1920, seed: int = 42) -> None:
    """Generate a single image via the Pollinations API wrapper.
    
    Args:
        prompt: Text description of the image.
        output_file: Destination path of the image.
        width: Generation width.
        height: Generation height.
        seed: Random generation seed.
    """
    try:
        # Create an image generator instance using pollinations Image class
        image_model = ai.Image(
            model='flux',
            width=width,
            height=height,
            seed=seed
        )
        
        # Call the generator model to download/render image
        image = image_model(prompt=prompt)
        
        # Save to disk
        image.save(output_file)
        logger.info("Saved image to: %s", output_file)
    except Exception as e:
        logger.error("Failed to generate image via Pollinations API: %s", e)
        raise
