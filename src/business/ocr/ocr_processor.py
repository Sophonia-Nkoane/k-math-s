from .ocr_setup import setup_local_ocr
import easyocr
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import re
import os
import logging
from typing import Dict, List, Any, Tuple, Optional, Callable
from utils.settings_manager import SettingsManager
from pprint import pprint
import subprocess
import platform

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# A threshold for pixel-based signature detection.
SIGNATURE_PIXEL_THRESHOLD = 200
# A lower zoom factor for the fallback OCR method to save resources.
OCR_ZOOM_FACTOR = 2.0 

# --- GPU Detection Cache ---
# Cache the GPU availability result to avoid repeated checks
_gpu_available_cache: Optional[bool] = None

# --- Fast GPU Detection Functions ---
def _check_nvidia_smi() -> bool:
    """Quick check for NVIDIA GPU using nvidia-smi command."""
    try:
        result = subprocess.run(['nvidia-smi'], 
                              capture_output=True, text=True, timeout=3)
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False

def _check_gpu_via_torch() -> bool:
    """Quick check for GPU using PyTorch if available."""
    try:
        import torch
        return torch.cuda.is_available() and torch.cuda.device_count() > 0
    except ImportError:
        return False

def _check_gpu_via_tensorflow() -> bool:
    """Quick check for GPU using TensorFlow if available."""
    try:
        import tensorflow as tf
        # Suppress TensorFlow logs during detection
        import os
        old_level = os.environ.get('TF_CPP_MIN_LOG_LEVEL', '0')
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
        
        # Quick GPU check
        gpus = tf.config.list_physical_devices('GPU')
        
        # Restore log level
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = old_level
        
        return len(gpus) > 0
    except (ImportError, Exception):
        return False

def is_gpu_available() -> bool:
    """Fast GPU availability check with caching. 
    
    Returns:
        bool: True if GPU is likely available for deep learning tasks
    """
    force_cpu = os.environ.get("OCR_FORCE_CPU", "1").strip().lower() in {"1", "true", "yes", "on"}
    if force_cpu:
        logging.info("OCR_FORCE_CPU is enabled - forcing CPU mode for OCR.")
        return False

    global _gpu_available_cache
    
    # Return cached result if available
    if _gpu_available_cache is not None:
        return _gpu_available_cache
    
    logging.info("Performing quick GPU availability check...")
    
    # Try multiple fast detection methods
    detection_methods = [
        ("nvidia-smi", _check_nvidia_smi),
        ("PyTorch", _check_gpu_via_torch),
        ("TensorFlow", _check_gpu_via_tensorflow)
    ]
    
    for method_name, check_func in detection_methods:
        try:
            if check_func():
                logging.info(f"GPU detected via {method_name}")
                _gpu_available_cache = True
                return True
        except Exception as e:
            logging.debug(f"GPU check via {method_name} failed: {e}")
            continue
    
    logging.info("No GPU detected - will use CPU for OCR")
    _gpu_available_cache = False
    return False

# --- Lazy-Loaded Global Reader ---
# We initialize this to None and only load it when it's first needed.
# This saves memory and startup time if we only process text-based PDFs.
reader: Optional[easyocr.Reader] = None

def get_reader() -> Optional[easyocr.Reader]:
    """Initializes the EasyOCR reader on first use (lazy loading)."""
    global reader
    if reader is None:
        try:
            settings = SettingsManager()
            model_dir = settings.get_system_setting('ocr_model_path')
            os.makedirs(model_dir, exist_ok=True) # Ensure the directory exists

            # Quick GPU availability check
            use_gpu = is_gpu_available()
            device_type = "GPU" if use_gpu else "CPU"
            
            logging.info(f"Initializing EasyOCR Reader for the first time (on {device_type})...")
            logging.info(f"Using model directory: {model_dir}")
            
            reader = easyocr.Reader(['en'], gpu=use_gpu, model_storage_directory=model_dir)
            logging.info(f"EasyOCR Reader initialized successfully on {device_type}.")
            
        except Exception as e:
            logging.error(f"Failed to initialize EasyOCR Reader. Error: {e}")
            # If GPU initialization failed, try CPU as fallback
            if use_gpu:
                logging.info("GPU initialization failed, falling back to CPU...")
                try:
                    reader = easyocr.Reader(['en'], gpu=False, model_storage_directory=model_dir)
                    logging.info("EasyOCR Reader initialized successfully on CPU (fallback).")
                    # Update cache to reflect that GPU didn't work
                    global _gpu_available_cache
                    _gpu_available_cache = False
                except Exception as e2:
                    logging.error(f"CPU fallback also failed: {e2}")
                    reader = None
            else:
                reader = None # Ensure it stays None on failure
    return reader

# --- Regex Constants (pre-compiled for performance) ---
AMOUNT_REGEX = re.compile(r'[R$€£]?\s*(\d+(?:[.,]\d{1,2})?)')
DATE_REGEX = re.compile(r'(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})')
GRADE_REGEX = re.compile(r'(?:Grade|Gr|Std)\.?\s*(\d{1,2})', re.IGNORECASE)
SIGNATURE_LINE_REGEX = re.compile(r'[_]{5,}')


# --- Core Processing Functions (Refactored) ---

def _process_page_with_full_ocr(
    page_image: Image.Image,
    page_num: int,
    file_path: str
) -> Tuple[Image.Image, List[Any]]:
    """
    The "Slow Path": Processes a single page image using full-page OCR.
    Used for image files or scanned PDFs.
    """
    ocr_reader = get_reader()
    if not ocr_reader:
        logging.error("OCR Reader not available. Cannot process image-based page.")
        return page_image, []

    logging.warning(f"Using fallback: Performing full OCR on page {page_num} of '{file_path}'.")
    
    # Preprocessing for better OCR on scanned documents
    preprocessed_image = page_image.convert('L').filter(ImageFilter.SHARPEN)
    image_np = np.array(preprocessed_image)
    
    ocr_results = ocr_reader.readtext(image_np, detail=1)
    
    logging.info(f"Finished full OCR on page {page_num}.")
    return (page_image, ocr_results)

def analyze_document(
    file_path: str,
    learner_names: List[str],
    progress_callback: Optional[Callable[[int, int], bool]] = None
) -> List[Dict[str, Any]]:
    """
    Analyzes a PDF or image file by choosing the most efficient method.
    
    Args:
        file_path: Path to the PDF or image file.
        learner_names: A list of learner names to search for.
        progress_callback: Optional callback for UI progress.

    Returns:
        A list of dictionaries containing the extracted data for each found learner.
    """
    _, extension = os.path.splitext(file_path.lower())
    
    if extension == ".pdf":
        return _analyze_pdf_fast_first(file_path, learner_names, progress_callback)
    elif extension in [".png", ".jpg", ".jpeg"]:
        return _analyze_image_file(file_path, learner_names, progress_callback)
    else:
        logging.warning(f"Unsupported file type for analysis: {extension}")
        return []

def _analyze_image_file(
    file_path: str,
    learner_names: List[str],
    progress_callback: Optional[Callable[[int, int], bool]] = None
) -> List[Dict[str, Any]]:
    """Handler for single image files, which always use the OCR path."""
    if progress_callback and not progress_callback(0, 1): return []
    
    try:
        image_rgb = Image.open(file_path).convert('RGB')
        page_image, ocr_results = _process_page_with_full_ocr(image_rgb, 1, file_path)
        
        # We need to package it like the main function expects
        processed_data = [(page_image, ocr_results)]
        results = extract_structured_data(processed_data, learner_names)

        if progress_callback: progress_callback(1, 1)
        return results
    except Exception as e:
        logging.error(f"Error processing image file {file_path}: {e}", exc_info=True)
        if progress_callback: progress_callback(-1, -1) # Signal error
        return []

def _analyze_pdf_fast_first(
    file_path: str,
    learner_names: List[str],
    progress_callback: Optional[Callable[[int, int], bool]] = None
) -> List[Dict[str, Any]]:
    """
    The "Fast Path" processor for PDFs. It tries direct text extraction first.
    If a page has no text (is a scan), it falls back to full OCR for that page.
    """
    all_results = []
    name_patterns = {name: re.compile(re.escape(name), re.IGNORECASE) for name in learner_names}

    try:
        doc = fitz.open(file_path)
        num_pages = len(doc)
        
        # This will hold the rendered page image. We only create it if we need it for signature checking.
        page_image: Optional[Image.Image] = None

        for i, page in enumerate(doc):
            if progress_callback and not progress_callback(i, num_pages):
                logging.info("Processing cancelled by user.")
                doc.close()
                return []

            # --- FAST PATH: Try direct text extraction ---
            text_blocks = page.get_text("blocks", sort=True)

            if not text_blocks:
                # --- SLOW PATH: No text found, it's a scanned image. Fallback to OCR. ---
                logging.warning(f"Page {i+1} has no text layer. Falling back to OCR.")
                mat = fitz.Matrix(OCR_ZOOM_FACTOR, OCR_ZOOM_FACTOR)
                pix = page.get_pixmap(matrix=mat)
                page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                
                _, ocr_results = _process_page_with_full_ocr(page_image, i + 1, file_path)
                page_data = [(page_image, ocr_results)]
                page_results = extract_structured_data(page_data, learner_names)
                all_results.extend(page_results)
                continue

            # --- If we are here, we are on the FAST PATH ---
            lines_with_details = []
            for block in text_blocks:
                # block format: (x0, y0, x1, y1, "text\n", block_no, block_type)
                # We only care about text blocks (type 0)
                if block[6] == 0:
                    lines_with_details.append({'text': block[4].strip(), 'box': block[:4]})

            for name, pattern in name_patterns.items():
                for line_idx, line_info in enumerate(lines_with_details):
                    if pattern.search(line_info['text']):
                        # Found a name, now search in its vicinity
                        context_start_idx = max(0, line_idx - 1)
                        context_end_idx = min(len(lines_with_details), line_idx + 4)
                        context_lines = lines_with_details[context_start_idx:context_end_idx]
                        context_str = ' '.join([l['text'] for l in context_lines])
                        
                        amount_match = AMOUNT_REGEX.search(context_str)
                        if not amount_match:
                            continue # A record without an amount is probably not what we want

                        grade_match = GRADE_REGEX.search(context_str)
                        date_match = DATE_REGEX.search(context_str)
                        is_signed = False

                        # Check for signature
                        for l in context_lines:
                            if SIGNATURE_LINE_REGEX.search(l['text']):
                                # We found a signature line, now we need the image to check pixels
                                if page_image is None:
                                    logging.info(f"Rendering page {i+1} to check signature...")
                                    mat = fitz.Matrix(OCR_ZOOM_FACTOR, OCR_ZOOM_FACTOR)
                                    pix = page.get_pixmap(matrix=mat)
                                    page_image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                                # The box from get_text is (x0, y0, x1, y1)
                                # We need to scale it to the rendered image size
                                scaled_box = tuple(coord * OCR_ZOOM_FACTOR for coord in l['box'])
                                if is_area_signed(page_image, scaled_box):
                                    is_signed = True
                                break
                        
                        try:
                            amount = float(amount_match.group(1).replace(',', '.'))
                        except (ValueError, IndexError):
                            amount = None

                        record = {
                            "name": name,
                            "grade": grade_match.group(1) if grade_match else None,
                            "date": date_match.group(1) if date_match else None,
                            "amount": amount,
                            "is_signed": is_signed
                        }
                        if record not in all_results:
                            all_results.append(record)
                        break # Move to the next learner name

        if progress_callback: progress_callback(num_pages, num_pages)
        doc.close()

    except Exception as e:
        logging.error(f"Error processing PDF file {file_path}: {e}", exc_info=True)
        if progress_callback: progress_callback(-1, -1)
        return []

    return all_results

# --- Helper Functions (Signature Check and OCR Data Parser) ---

def is_area_signed(image: Image.Image, box: Tuple[int, int, int, int]) -> bool:
    """Analyzes pixels within a bounding box to find a signature."""
    try:
        signature_area = image.crop(box)
        # Convert to grayscale and binarize. Pixels < 150 are considered 'ink'.
        binary_image = signature_area.convert('L').point(lambda p: 0 if p < 150 else 255, '1')
        binary_array = np.array(binary_image)
        ink_pixel_count = np.sum(binary_array == 0) # Count black pixels
        logging.debug(f"Signature area {box} has {ink_pixel_count} ink pixels.")
        return ink_pixel_count > SIGNATURE_PIXEL_THRESHOLD
    except Exception as e:
        logging.error(f"Could not analyze signature area {box}: {e}")
        return False

def extract_structured_data(
    processed_pages_ocr: List[Tuple[Image.Image, List[Any]]],
    learner_names: List[str]
) -> List[Dict[str, Any]]:
    """
    Finds learner names and details from OCR data for attendance.
    """
    all_results = []
    name_surname_map = {}
    name_patterns = {}

    for full_name in learner_names:
        parts = full_name.split(', ')
        if len(parts) == 2:
            surname = parts[0]
            name = parts[1]
            name_surname_map[full_name] = (name, surname)
            name_patterns[full_name] = re.compile(re.escape(full_name), re.IGNORECASE)
        else:
            name_parts = full_name.split(' ', 1)
            name = name_parts[0]
            surname = name_parts[1] if len(name_parts) > 1 else ""
            name_surname_map[full_name] = (name, surname)
            name_patterns[full_name] = re.compile(re.escape(full_name), re.IGNORECASE)


    for page_image, ocr_data in processed_pages_ocr:
        lines_with_details = [(item[1], item[0]) for item in ocr_data]  # (text, box_coords)

        for full_name, pattern in name_patterns.items():
            for i, (line_text, line_box_poly) in enumerate(lines_with_details):
                if pattern.search(line_text):
                    context_end_index = min(len(lines_with_details), i + 3)
                    context_items = lines_with_details[i:context_end_index]
                    context_str = ' '.join([item[0] for item in context_items])

                    date_match = DATE_REGEX.search(context_str)
                    is_signed = False

                    for text, box_poly in context_items:
                        if SIGNATURE_LINE_REGEX.search(text):
                            x_coords = [p[0] for p in box_poly]
                            y_coords = [p[1] for p in box_poly]
                            image_box = (min(x_coords), min(y_coords), max(x_coords), max(y_coords))
                            if is_area_signed(page_image, image_box):
                                is_signed = True
                            break

                    name, surname = name_surname_map[full_name]

                    record = {
                        "name": name,
                        "surname": surname,
                        "date": date_match.group(1) if date_match else None,
                        "is_signed": is_signed
                    }
                    if record not in all_results:
                        all_results.append(record)
                    break
    return all_results

# --- Example Usage (Updated) ---
def create_test_image(file_path: str):
    """Creates a dummy image for testing."""
    img = Image.new('RGB', (800, 600), color='white')
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 20)
        small_font = ImageFont.truetype("arial.ttf", 15)
    except IOError:
        logging.warning("Arial font not found. Using default font.")
        font = ImageFont.load_default()
        small_font = font

    draw.text((50, 50), "Learner Payment Sheet", fill='black', font=font)
    draw.text((50, 80), "Date: 2024-09-01", fill='black', font=small_font)
    draw.text((50, 150), "1. John Doe - Grade 5 - R150.50", fill='black', font=font)
    draw.text((70, 180), "Signature: ________________________", fill='black', font=font)
    # Simulate a signature
    draw.line((220, 195, 260, 185), fill='blue', width=2)
    draw.line((260, 185, 300, 198), fill='blue', width=2)
    draw.line((300, 198, 350, 188), fill='blue', width=2)
    draw.text((50, 250), "2. Jane Smith - Grade 7 - R200.00", fill='black', font=font)
    draw.text((70, 280), "Signature: ________________________", fill='black', font=font) # Unsigned
    img.save(file_path)
    logging.info(f"Test image created at {file_path}")

if __name__ == '__main__':
    test_file_path = "test_document.png"
    create_test_image(test_file_path)

    learner_list = ["John Doe", "Jane Smith", "Peter Jones"]

    # The new, unified entry point
    logging.info(f"--- Analyzing Document: {test_file_path} ---")
    extracted_data = analyze_document(test_file_path, learner_list)

    logging.info("--- Extracted Structured Data ---")
    if extracted_data:
        pprint(extracted_data)
    else:
        logging.info("No matching records found.")
    
    # To test with a PDF, you would just change the path.
    # For a text-based PDF, you'll notice it runs much faster and might not
    # even print the "Initializing EasyOCR" message if no signatures need checking.
    # test_pdf_path = "path/to/your/document.pdf"
    # extracted_data_pdf = analyze_document(test_pdf_path, learner_list)
    # pprint(extracted_data_pdf)
