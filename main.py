#!/usr/bin/env python3
"""
Shortrocity - AI Automated Short Video Generator CLI
"""

import os
import sys
import json
import time
import argparse
import logging
import google.generativeai as genai

import config
import narration
import images
import video

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Fallback script content if API calls are rate-limited or fail
FALLBACK_SCRIPT = """###

[A close-up of a hand holding a smartphone displaying a social media application]

Narrator: "This isn't a plot twist per se, but I met a guy online a few years ago and we started hanging out and became good friends."

[An image of two people laughing and talking in a casual setting]

Narrator: "In 2016 he got a Facebook message from a young man telling him that he was his father."

[A close-up of a smartphone screen displaying a Facebook message]

Narrator: "He gave his mother's name and sure enough my friend had slept with her a few times around when he would have been conceived." 

[A blurry image of a couple interacting in a bar or party setting]

Narrator: "He showed me the young guy's Facebook page and there was a picture of his mother, who looked very familiar to me."

[A close-up of a smartphone displaying a Facebook profile with a picture of a woman]

Narrator: "I looked at her profile, and sure enough, it was my best friend from high school's older sister." 

[A picture of two friends smiling and laughing together]

Narrator: "She had a kid when she was 16 and he lived with my best friend for a couple of years and I would babysit him quite a bit."

[A picture of a person holding a baby in their arms]

Narrator: "I have about half a dozen photos of me with him when he was a baby."

[A picture of a photo album filled with baby pictures]

Narrator: "This is the best story that you haven't heard, and watch till the end." 
"""

def generate_script_with_gemini(topic: str) -> str:
    """Generate the narration script using Gemini AI.
    
    Args:
        topic: The text prompt or story description.
        
    Returns:
        The raw generated script string.
    """
    logger.info("Connecting to Gemini API using model '%s'...", config.GEMINI_MODEL_NAME)
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
    
    prompt = f"""You are a YouTube short narration generator. You generate 30 seconds to 1 minute of narration. The shorts you create have a background that fades from image to image as the narration is going on.

    You will need to generate descriptions of images for each of the sentences in the short. They will be passed to an AI image generator. DO NOT IN ANY CIRCUMSTANCES use names of celebrities or people in the image descriptions. It is illegal to generate images of celebrities. Only describe persons without their names. Do not reference any real person or group in the image descriptions. Don't mention the female figure or other sexual content in the images because they are not allowed.

    You are however allowed to use any content, including real names in the narration. Only image descriptions are restricted.

    Note that the narration will be fed into a text-to-speech engine, so don't use special characters.

    Respond with a pair of an image description in square brackets and a narration below it. Both of them should be on their own lines, as follows:

    ###

    [Description of a background image]

    Narrator: "One sentence of narration"

    [Description of a background image]

    Narrator: "One sentence of narration"

    [Description of a background image]

    Narrator: "One sentence of narration"

    ###

    The short should be 15 sentences maximum.

    You should add a description of a fitting background image in between all of the narrations. It will later be used to generate an image with AI.
    start with this the best story that you havent heard and watch till the end .
    Create a YouTube short of {topic} .
    """
    
    response = model.generate_content(prompt)
    return str(response.candidates[0].content.parts[0].text)

def main():
    parser = argparse.ArgumentParser(
        description="Shortrocity: AI-Powered Automated Short Video Generator",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-t", "--topic", 
        type=str, 
        help="The topic or story description to generate a video for."
    )
    parser.add_argument(
        "-s", "--source", 
        type=str, 
        help="Path to a text file containing the source story or riddles."
    )
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="final_video.mp4", 
        help="Output filename for the compiled video."
    )
    parser.add_argument(
        "--offline", 
        action="store_true", 
        help="Run in offline mode using the cached fallback script (ideal for API limits)."
    )
    
    args = parser.parse_args()

    # Welcome header
    print("=" * 60)
    print("          SHORTROCITY - AUTOMATED AI SHORTS GENERATOR          ")
    print("=" * 60)
    
    # Run environment checks
    warnings = config.validate_environment()
    if warnings:
        logger.warning("Configuration Check:")
        for w in warnings:
            print(f"  - {w}")
        print("-" * 60)

    # Determine topic / source text
    topic_content = ""
    if args.topic:
        topic_content = args.topic
    elif args.source:
        if os.path.exists(args.source):
            with open(args.source, "r", encoding="utf-8") as f:
                topic_content = f.read()
            logger.info("Loaded source content from file: %s", args.source)
        else:
            logger.error("Source file not found: %s", args.source)
            sys.exit(1)
    else:
        # Default topic
        topic_content = (
            "Not a plot twist per se, but I met a guy online a few years ago and we started hanging out and became good friends. "
            "In 2016 he got a facebook message from a young man telling him that he was his father. He gave his mother's name and "
            "sure enough my friend had slept with her a few times around when he would have been conceived. He showed me the young "
            "guy's Facebook page and there was a picture of his mother, who looked very familiar to me. I looked at her profile, "
            "and sure enough, it was my best friend from high school older sister. She had a kid when she was 16 and he lived with "
            "my best friend for a couple of years and I would babysit him quite a bit. I have about half a dozen photos of me with "
            "him when he was a baby."
        )
        logger.info("No topic provided. Using default story.")

    # Create run directory
    short_id = str(int(time.time()))
    basedir = os.path.join(config.SHORTS_DIR, short_id)
    if not os.path.exists(basedir):
        os.makedirs(basedir)
    logger.info("Session directory created at: %s", basedir)

    # Step 1: Script Generation
    response_text = ""
    if args.offline:
        logger.info("Offline mode active. Utilizing cached fallback script...")
        response_text = FALLBACK_SCRIPT
    else:
        try:
            response_text = generate_script_with_gemini(topic_content)
            logger.info("Script successfully generated via Gemini AI.")
        except Exception as e:
            logger.error("Gemini script generation failed: %s", e)
            logger.info("Falling back to cached script response to continue generation...")
            response_text = FALLBACK_SCRIPT

    # Write script output to file
    script_path = os.path.join(basedir, "response.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(response_text)
    logger.info("Script response written to %s", script_path)

    # Step 2: Parse Script
    logger.info("Parsing script segments...")
    data, narrations = narration.parse(response_text, basedir)

    # Step 3: Text-to-Speech (TTS)
    logger.info("Generating voice narration files...")
    narration.create(data, os.path.join(basedir, "narrations"))

    # Step 4: AI Image Generation
    logger.info("Generating visual scenes via Pollinations (Flux)...")
    images.create_from_data(data, os.path.join(basedir, "images"))

    # Step 5: Video compilation & Subtitling
    logger.info("Compiling final video and burning subtitles...")
    video.create_video_with_captions(
        narrations=narrations,
        output_dir=basedir,
        output_filename=args.output
    )

    print("=" * 60)
    print(f"SUCCESS: Video generation completed!")
    print(f"Output File: {os.path.join(basedir, args.output)}")
    print("=" * 60)

if __name__ == "__main__":
    main()
