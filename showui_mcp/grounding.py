"""
ShowUI-2B model wrapper for GUI element grounding.
Loads model once, keeps it resident on GPU for fast repeated inference.
"""
import ast
import time
import logging
from pathlib import Path

import torch
from PIL import Image
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Based on the screenshot of the page, I give a text description and you give its "
    "corresponding location. The coordinate represents a clickable location [x, y] for "
    "an element, which is a relative coordinate on the screenshot, scaled from 0 to 1."
)

MIN_PIXELS = 256 * 28 * 28
MAX_PIXELS = 1344 * 28 * 28
MODEL_ID = "showlab/ShowUI-2B"


class ShowUIGrounder:
    """Loads ShowUI-2B and provides GUI element grounding."""

    def __init__(self):
        self.model = None
        self.processor = None
        self._loaded = False

    def load(self):
        """Load model onto GPU. Called once at server startup."""
        if self._loaded:
            return
        logger.info("Loading ShowUI-2B model (%s)...", MODEL_ID)
        start = time.time()

        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.bfloat16,
            device_map="auto",
        )
        self.processor = AutoProcessor.from_pretrained(
            MODEL_ID,
            min_pixels=MIN_PIXELS,
            max_pixels=MAX_PIXELS,
        )
        self._loaded = True
        vram = torch.cuda.memory_allocated() / 1024**3
        logger.info("Model loaded in %.1fs, VRAM: %.1f GB", time.time() - start, vram)

    def ground(self, image_path: str, query: str) -> dict:
        """
        Locate a UI element in the screenshot.

        Args:
            image_path: Absolute path to a screenshot PNG/JPG.
            query: Description of the element to find (e.g. "同意" or "the Submit button").

        Returns:
            dict with keys: nx, ny (normalized 0-1), px, py (pixel), width, height, inference_time
        """
        if not self._loaded:
            self.load()

        image = Image.open(image_path).convert("RGB")
        w, h = image.size

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _SYSTEM_PROMPT},
                    {"type": "image", "image": image_path, "min_pixels": MIN_PIXELS, "max_pixels": MAX_PIXELS},
                    {"type": "text", "text": query},
                ],
            }
        ]

        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, video_inputs = process_vision_info(messages)
        inputs = self.processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            padding=True,
            return_tensors="pt",
        ).to("cuda")

        start = time.time()
        with torch.no_grad():
            generated_ids = self.model.generate(**inputs, max_new_tokens=128)
        inference_time = time.time() - start

        generated_ids_trimmed = [
            out_ids[len(in_ids):] for in_ids, out_ids in zip(inputs.input_ids, generated_ids)
        ]
        output_text = self.processor.batch_decode(
            generated_ids_trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False
        )[0].strip()

        logger.info("Query=%r -> %s (%.1fs)", query, output_text, inference_time)

        try:
            coords = ast.literal_eval(output_text)
            if isinstance(coords, list) and len(coords) == 2:
                nx, ny = float(coords[0]), float(coords[1])
                return {
                    "success": True,
                    "nx": nx,
                    "ny": ny,
                    "px": int(nx * w),
                    "py": int(ny * h),
                    "width": w,
                    "height": h,
                    "inference_time": round(inference_time, 2),
                    "raw_output": output_text,
                }
        except (ValueError, SyntaxError):
            pass

        return {
            "success": False,
            "error": f"Could not parse coordinates from model output: {output_text}",
            "raw_output": output_text,
            "inference_time": round(inference_time, 2),
            "width": w,
            "height": h,
        }

    def ground_batch(self, image_path: str, queries: list[str]) -> list[dict]:
        """Locate multiple UI elements in the same screenshot."""
        results = []
        for q in queries:
            results.append(self.ground(image_path, q))
        return results
