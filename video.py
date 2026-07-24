import os
import math
import cv2
import numpy as np
import subprocess
import logging
from typing import List, Dict, Any
from pydub import AudioSegment
import assemblyai as aai
import sys
import config

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configure AssemblyAI
aai.settings.api_key = config.ASSEMBLYAI_API_KEY
transcriber = aai.Transcriber()

# Dynamically locate and configure local ffmpeg/ffprobe binaries for pydub
ffmpeg_bin, ffprobe_bin = config.get_ffmpeg_binaries()
AudioSegment.converter = ffmpeg_bin
AudioSegment.ffprobe = ffprobe_bin

logger.info("Configured pydub: converter=%s, ffprobe=%s", ffmpeg_bin, ffprobe_bin)

def resize_image_aspect_ratio(image: np.ndarray, target_width: int = 576, target_height: int = 1024) -> np.ndarray:
    """Crop and resize an image to match target aspect ratio without distortion.
    
    Args:
        image: The source OpenCV image.
        target_width: Desired width of output image.
        target_height: Desired height of output image.
        
    Returns:
        The cropped and resized image.
    """
    height, width = image.shape[:2]
    target_aspect = target_width / target_height
    current_aspect = width / height

    if current_aspect > target_aspect:
        # Image is wider than target aspect ratio -> crop width
        new_width = int(height * target_aspect)
        x_offset = (width - new_width) // 2
        image = image[:, x_offset:x_offset + new_width]
    elif current_aspect < target_aspect:
        # Image is taller than target aspect ratio -> crop height
        new_height = int(width / target_aspect)
        y_offset = (height - new_height) // 2
        image = image[y_offset:y_offset + new_height, :]
    
    return cv2.resize(image, (target_width, target_height))

def get_audio_duration(audio_file: str) -> int:
    """Get the duration of an audio file in milliseconds.
    
    Args:
        audio_file: Path to the audio file.
        
    Returns:
        Duration in milliseconds.
    """
    try:
        segment = AudioSegment.from_file(audio_file)
        return len(segment)
    except Exception as e:
        logger.error("Failed to read audio duration for %s: %s", audio_file, e)
        raise

def transcribe_with_assemblyai(audio_file: str) -> List[Dict[str, Any]]:
    """Upload and transcribe audio using AssemblyAI to get words with timestamps.
    
    Args:
        audio_file: Path to the audio file.
        
    Returns:
        List of transcribed words with start/end timestamps.
    """
    try:
        transcript = transcriber.transcribe(audio_file)
        if transcript.status == aai.TranscriptStatus.error:
            raise Exception(transcript.error)
        return transcript.json_response.get('words', [])
    except Exception as e:
        logger.error("AssemblyAI transcription failed: %s", e)
        raise

def add_narration_to_video(narrations: List[str], input_video: str, output_dir: str, output_file: str) -> None:
    """Concatenate individual narration audio clips and mux them into the video.
    
    Args:
        narrations: List of raw narration sentences.
        input_video: Path to the input video.
        output_dir: Parent output directory.
        output_file: Destination file name for the muxed video.
    """
    logger.info("Muxing narrations audio with video...")
    full_narration = AudioSegment.empty()
    for i in range(len(narrations)):
        audio_path = os.path.join(output_dir, "narrations", f"narration_{i+1}.mp3")
        full_narration += AudioSegment.from_file(audio_path)
        
    temp_narration = os.path.join(output_dir, "narration_full_temp.mp3")
    full_narration.export(temp_narration, format="mp3")

    ffmpeg_bin, _ = config.get_ffmpeg_binaries()
    dest_path = os.path.join(output_dir, output_file)
    
    ffmpeg_command = [
        ffmpeg_bin,
        '-y',
        '-i', input_video,
        '-i', temp_narration,
        '-map', '0:v',   # Map video from the first input
        '-map', '1:a',   # Map audio from the second input
        '-c:v', 'copy',  # Copy video codec directly
        '-c:a', 'aac',   # AAC audio codec
        '-strict', 'experimental',
        dest_path
    ]
    
    logger.info("Running FFmpeg audio muxing: %s", " ".join(ffmpeg_command))
    result = subprocess.run(ffmpeg_command, capture_output=True)
    
    if os.path.exists(temp_narration):
        os.remove(temp_narration)
        
    if result.returncode != 0:
        logger.error("FFmpeg audio muxing failed: %s", result.stderr.decode())
        raise Exception("FFmpeg audio muxing failed.")
    logger.info("Audio narration added successfully.")

def create_video_with_captions(
    narrations: List[str], 
    output_dir: str, 
    output_filename: str, 
    width: int = config.DEFAULT_WIDTH, 
    height: int = config.DEFAULT_HEIGHT, 
    fps: int = config.DEFAULT_FPS, 
    fade_duration: int = config.DEFAULT_FADE_DURATION_MS
) -> None:
    """Compile generated images into a video with smooth transitions and burnt-in subtitles.
    
    Args:
        narrations: List of narration sentences.
        output_dir: Output directory containing 'images' and 'narrations' folders.
        output_filename: Final filename for the compiled video.
        width: Video width.
        height: Video height.
        fps: Video frames per second.
        fade_duration: Cross-fade transition length in milliseconds.
    """
    output_dir = os.path.abspath(output_dir)
    logger.info("Initializing video creation inside: %s", output_dir)
    
    temp_video_path = os.path.join(output_dir, "temp_video.avi")
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter(temp_video_path, fourcc, fps, (width, height))

    images_dir = os.path.join(output_dir, "images")
    image_paths = sorted([f for f in os.listdir(images_dir) if f.endswith('.jpg') or f.endswith('.png')])
    image_count = len(image_paths)

    if image_count == 0:
        raise ValueError(f"No images found in {images_dir} to construct video.")

    for i in range(image_count):
        img_path = os.path.join(images_dir, f"image_{i}.jpg")
        image1 = cv2.imread(img_path)
        if image1 is None:
            logger.warning("Could not read image %s. Skipping scene.", img_path)
            continue
            
        image1 = resize_image_aspect_ratio(image1, target_width=width, target_height=height)
        
        # Load next image for transition, looping back to start at the end
        next_img_path = os.path.join(images_dir, f"image_{(i+1) % image_count}.jpg")
        image2 = cv2.imread(next_img_path)
        if image2 is None:
            image2 = image1.copy()
        else:
            image2 = resize_image_aspect_ratio(image2, target_width=width, target_height=height)

        narration_file = os.path.join(output_dir, "narrations", f"narration_{i+1}.mp3")
        duration = get_audio_duration(narration_file)
        
        # Write frames for the duration of the current narration sentence
        num_main_frames = math.floor(duration / 1000 * fps)
        for _ in range(num_main_frames):
            out.write(image1)
            
        # Write transition/fading frames
        num_fade_frames = math.floor(fade_duration / 1000 * fps)
        for alpha in np.linspace(0, 1, num_fade_frames):
            blended_image = cv2.addWeighted(image1, 1 - alpha, image2, alpha, 0)
            out.write(blended_image)
    
    out.release()
    logger.info("OpenCV raw video writer released.")
    
    # Merge audio
    temp_audio_video = "temp_audio_video.mp4"
    add_narration_to_video(narrations, temp_video_path, output_dir, temp_audio_video)

    # Transcribe and burn captions
    logger.info("Transcribing audio segments for captions...")
    segments = create_segments_with_assemblyai(narrations, output_dir)
    
    logger.info("Burning captions onto video...")
    add_captions_to_video(
        segments, 
        os.path.join(output_dir, temp_audio_video), 
        output_dir, 
        output_filename
    )
    
    # Cleanup temp video frames
    if os.path.exists(temp_video_path):
        os.remove(temp_video_path)
        
    # Cleanup temp audio-video file
    temp_audio_video_path = os.path.join(output_dir, temp_audio_video)
    if os.path.exists(temp_audio_video_path):
        try:
            os.remove(temp_audio_video_path)
        except Exception as e:
            logger.warning("Could not delete temporary file %s: %s", temp_audio_video, e)

def create_segments_with_assemblyai(narrations: List[str], output_dir: str) -> List[Dict[str, Any]]:
    """Assemble word-level transcription segments mapped to global video timeline.
    
    Args:
        narrations: List of narrations.
        output_dir: Video directory.
        
    Returns:
        List of segments with start, end times and words.
    """
    segments = []
    offset = 0.0

    for i, narration in enumerate(narrations):
        narration_path = os.path.join(output_dir, "narrations", f"narration_{i+1}.mp3")
        words = transcribe_with_assemblyai(narration_path)

        for word in words:
            segments.append({
                "start": word["start"] / 1000 + offset,
                "end": word["end"] / 1000 + offset,
                "text": word["text"]
            })

        offset += get_audio_duration(narration_path) / 1000

    return segments

def format_time_srt(seconds: float) -> str:
    """Format seconds into SRT subtitle format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"

def add_captions_to_video(segments: List[Dict[str, Any]], input_video: str, output_dir: str, output_filename: str) -> None:
    """Burn subtitles directly into the video file using FFmpeg subtitles filter.
    
    Args:
        segments: Word timestamps list.
        input_video: Source video path.
        output_dir: Target directory.
        output_filename: Output file name.
    """
    captions_path = os.path.join(output_dir, "captions.srt")
    
    with open(captions_path, 'w', encoding='utf-8') as f:
        for i, segment in enumerate(segments, start=1):
            start_time = format_time_srt(segment['start'])
            end_time = format_time_srt(segment['end'])
            caption_text = segment['text']
            
            f.write(f"{i}\n")
            f.write(f"{start_time} --> {end_time}\n")
            f.write(f"{caption_text}\n\n")

    output_path = os.path.join(output_dir, output_filename)
    logger.info("Subtitled output path: %s", output_path)

    # Escape path characters for subtitles filter (especially for cross-platform backslashes/colons)
    safe_captions_path = captions_path.replace("\\", "/").replace(":", "\\:")
    
    ffmpeg_bin, _ = config.get_ffmpeg_binaries()
    
    ffmpeg_command = [
        ffmpeg_bin,
        '-y',
        '-i', input_video,
        '-filter_complex', f"subtitles='{safe_captions_path}':force_style='Alignment={config.CAPTION_ALIGNMENT},MarginV={config.CAPTION_MARGIN_V},Fontsize={config.CAPTION_FONT_SIZE}'",
        output_path
    ]
    
    logger.info("Running FFmpeg burning subtitles: %s", " ".join(ffmpeg_command))
    result = subprocess.run(ffmpeg_command, capture_output=True)
    
    if result.returncode != 0:
        logger.error("FFmpeg subtitles burning failed: %s", result.stderr.decode())
        raise Exception("FFmpeg subtitles burning failed.")
    
    logger.info("Subtitles burned successfully. Final output: %s", output_path)
