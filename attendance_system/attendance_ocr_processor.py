"""
Attendance OCR Processor

This module provides OCR processing specifically for the attendance system,
decoupled from the payment system's OCR functionality but maintaining
compatibility for payment data extraction.
"""

import logging
import re
import os
from datetime import date, datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import io

# Import from attendance models
from attendance_models.attendance_models import (
    OCRResult, AttendanceRecord, PaymentFeedData, AttendanceStatus
)


# Regex patterns for data extraction
AMOUNT_REGEX = re.compile(r'[R$€£]?\s*(\d+(?:[.,]\d{1,2})?)')
DATE_REGEX = re.compile(r'(\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4})')
GRADE_REGEX = re.compile(r'(?:Grade|Gr|Std)\.?\s*(\d{1,2})', re.IGNORECASE)
SIGNATURE_LINE_REGEX = re.compile(r'[_]{5,}')
NAME_REGEX = re.compile(r'^([A-Za-z]+)\s+([A-Za-z]+)$')


class AttendanceOCRProcessor:
    """
    OCR Processor specifically for attendance documents.
    
    This processor handles:
    1. Attendance sheet scanning and learner identification
    2. Signature detection for attendance verification
    3. Payment slip processing (for payment feed integration)
    4. Learner name matching and validation
    """
    
    def __init__(self, learner_list: List[Dict[str, Any]] = None):
        """
        Initialize the attendance OCR processor.
        
        Args:
            learner_list: List of learner dictionaries with keys:
                         - acc_no, name, surname, grade
        """
        self.learner_list = learner_list or []
        self.logger = logging.getLogger(__name__)
        
        # Build name lookup maps for efficient matching
        self._build_name_lookup_maps()
        
        # OCR reader (lazy loaded)
        self._ocr_reader = None
    
    def _build_name_lookup_maps(self):
        """Build lookup maps for efficient learner name matching."""
        self._name_to_learner = {}
        self._surname_to_learners = {}
        self._full_name_to_learner = {}
        
        for learner in self.learner_list:
            name = learner.get('name', '').strip().lower()
            surname = learner.get('surname', '').strip().lower()
            acc_no = learner.get('acc_no', '')
            grade = learner.get('grade', 1)
            
            # Full name lookup
            full_name = f"{name} {surname}"
            self._full_name_to_learner[full_name] = {
                'acc_no': acc_no,
                'name': learner.get('name', ''),
                'surname': learner.get('surname', ''),
                'grade': grade
            }
            
            # Surname, Name format
            reverse_name = f"{surname}, {name}"
            self._full_name_to_learner[reverse_name] = {
                'acc_no': acc_no,
                'name': learner.get('name', ''),
                'surname': learner.get('surname', ''),
                'grade': grade
            }
            
            # Name to learner mapping
            if name not in self._name_to_learner:
                self._name_to_learner[name] = []
            self._name_to_learner[name].append({
                'acc_no': acc_no,
                'surname': learner.get('surname', ''),
                'grade': grade
            })
    
    def update_learner_list(self, learner_list: List[Dict[str, Any]]):
        """Update the learner list for matching."""
        self.learner_list = learner_list
        self._build_name_lookup_maps()
    
    def process_document(
        self, 
        file_path: str,
        extract_payments: bool = True
    ) -> List[OCRResult]:
        """
        Process a document (PDF or image) for attendance data.
        
        Args:
            file_path: Path to the document file
            extract_payments: Whether to also extract payment data
            
        Returns:
            List of OCRResult objects
        """
        _, extension = os.path.splitext(file_path.lower())
        
        if extension == '.pdf':
            return self._process_pdf(file_path, extract_payments)
        elif extension in ['.png', '.jpg', '.jpeg']:
            return self._process_image(file_path, extract_payments)
        else:
            self.logger.warning(f"Unsupported file type: {extension}")
            return []
    
    def _process_pdf(
        self, 
        file_path: str, 
        extract_payments: bool
    ) -> List[OCRResult]:
        """Process a PDF document."""
        results = []
        
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(file_path)
            
            for page_num, page in enumerate(doc):
                # Try direct text extraction first
                text_blocks = page.get_text("blocks", sort=True)
                
                if text_blocks:
                    # Process text-based PDF
                    page_results = self._process_text_blocks(
                        text_blocks, page_num + 1, extract_payments
                    )
                    results.extend(page_results)
                else:
                    # Fall back to OCR for scanned PDFs
                    self.logger.info(f"Page {page_num + 1} requires OCR")
                    page_results = self._process_page_with_ocr(
                        page, page_num + 1, extract_payments
                    )
                    results.extend(page_results)
            
            doc.close()
            
        except ImportError:
            self.logger.warning("PyMuPDF not available, cannot process PDF")
        except Exception as e:
            self.logger.error(f"Error processing PDF {file_path}: {e}")
        
        return results
    
    def _process_image(
        self, 
        file_path: str, 
        extract_payments: bool
    ) -> List[OCRResult]:
        """Process an image file."""
        try:
            from PIL import Image
            
            image = Image.open(file_path)
            return self._process_image_with_ocr(image, 1, extract_payments)
            
        except ImportError:
            self.logger.warning("PIL not available, cannot process image")
        except Exception as e:
            self.logger.error(f"Error processing image {file_path}: {e}")
        
        return []
    
    def _process_text_blocks(
        self, 
        text_blocks: List,
        page_num: int,
        extract_payments: bool
    ) -> List[OCRResult]:
        """Process text blocks extracted from a PDF."""
        results = []
        
        for block in text_blocks:
            if block[6] != 0:  # Skip non-text blocks
                continue
            
            text = block[4].strip()
            lines = text.split('\n')
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Try to match learner name
                learner_match = self._match_learner_name(line)
                
                if learner_match:
                    # Extract additional data from context
                    context = self._get_context_around_block(text_blocks, block)
                    
                    # Check for signature
                    is_signed = SIGNATURE_LINE_REGEX.search(context) is not None
                    
                    # Extract date
                    date_match = DATE_REGEX.search(context)
                    record_date = None
                    if date_match:
                        record_date = self._parse_date(date_match.group(1))
                    
                    # Extract payment if requested
                    payment_amount = None
                    if extract_payments:
                        amount_match = AMOUNT_REGEX.search(context)
                        if amount_match:
                            try:
                                payment_amount = float(amount_match.group(1).replace(',', '.'))
                            except ValueError:
                                pass
                    
                    result = OCRResult(
                        success=True,
                        learner_name=learner_match['name'],
                        learner_surname=learner_match['surname'],
                        learner_acc_no=learner_match['acc_no'],
                        grade=learner_match.get('grade'),
                        date=record_date or date.today(),
                        is_signed=is_signed,
                        payment_amount=payment_amount
                    )
                    results.append(result)
        
        return results
    
    def _process_page_with_ocr(
        self, 
        page,
        page_num: int,
        extract_payments: bool
    ) -> List[OCRResult]:
        """Process a PDF page using OCR."""
        results = []
        
        try:
            # Lazy load OCR reader
            if self._ocr_reader is None:
                self._ocr_reader = self._initialize_ocr_reader()
            
            if self._ocr_reader is None:
                self.logger.warning("OCR reader not available")
                return results
            
            import fitz
            from PIL import Image
            import numpy as np
            
            # Render page to image
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better OCR
            pix = page.get_pixmap(matrix=mat)
            image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            
            # Convert to numpy array for OCR
            image_np = np.array(image.convert('L'))
            
            # Run OCR
            ocr_results = self._ocr_reader.readtext(image_np, detail=1)
            
            # Process OCR results
            results = self._process_ocr_results(
                ocr_results, image, page_num, extract_payments
            )
            
        except Exception as e:
            self.logger.error(f"Error in OCR processing: {e}")
        
        return results
    
    def _process_image_with_ocr(
        self, 
        image,
        page_num: int,
        extract_payments: bool
    ) -> List[OCRResult]:
        """Process an image using OCR."""
        results = []
        
        try:
            # Lazy load OCR reader
            if self._ocr_reader is None:
                self._ocr_reader = self._initialize_ocr_reader()
            
            if self._ocr_reader is None:
                self.logger.warning("OCR reader not available")
                return results
            
            import numpy as np
            
            # Convert to numpy array for OCR
            image_np = np.array(image.convert('L'))
            
            # Run OCR
            ocr_results = self._ocr_reader.readtext(image_np, detail=1)
            
            # Process OCR results
            results = self._process_ocr_results(
                ocr_results, image, page_num, extract_payments
            )
            
        except Exception as e:
            self.logger.error(f"Error in image OCR processing: {e}")
        
        return results
    
    def _process_ocr_results(
        self, 
        ocr_results: List,
        image,
        page_num: int,
        extract_payments: bool
    ) -> List[OCRResult]:
        """Process OCR results and extract attendance data."""
        results = []
        
        # Build lines with positions
        lines_with_positions = []
        for item in ocr_results:
            text = item[1]
            box = item[0]
            confidence = item[2] if len(item) > 2 else 1.0
            
            lines_with_positions.append({
                'text': text,
                'box': box,
                'confidence': confidence
            })
        
        # Process each line
        for i, line_info in enumerate(lines_with_positions):
            text = line_info['text'].strip()
            
            # Try to match learner name
            learner_match = self._match_learner_name(text)
            
            if learner_match:
                # Get context (surrounding lines)
                context_start = max(0, i - 2)
                context_end = min(len(lines_with_positions), i + 4)
                context_lines = lines_with_positions[context_start:context_end]
                context_text = ' '.join([l['text'] for l in context_lines])
                
                # Check for signature
                is_signed = self._check_signature_in_context(
                    context_lines, image, line_info
                )
                
                # Extract date
                date_match = DATE_REGEX.search(context_text)
                record_date = None
                if date_match:
                    record_date = self._parse_date(date_match.group(1))
                
                # Extract payment if requested
                payment_amount = None
                if extract_payments:
                    amount_match = AMOUNT_REGEX.search(context_text)
                    if amount_match:
                        try:
                            payment_amount = float(amount_match.group(1).replace(',', '.'))
                        except ValueError:
                            pass
                
                result = OCRResult(
                    success=True,
                    learner_name=learner_match['name'],
                    learner_surname=learner_match['surname'],
                    learner_acc_no=learner_match['acc_no'],
                    grade=learner_match.get('grade'),
                    date=record_date or date.today(),
                    is_signed=is_signed,
                    payment_amount=payment_amount,
                    confidence_score=line_info['confidence']
                )
                results.append(result)
        
        return results
    
    def _match_learner_name(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Try to match a learner name from the text.
        
        Args:
            text: Text to search for learner name
            
        Returns:
            Learner dictionary if found, None otherwise
        """
        text_lower = text.strip().lower()
        
        # Direct full name match
        if text_lower in self._full_name_to_learner:
            return self._full_name_to_learner[text_lower]
        
        # Try to extract name parts
        name_match = NAME_REGEX.match(text.strip())
        if name_match:
            first_name = name_match.group(1).lower()
            last_name = name_match.group(2).lower()
            full_name = f"{first_name} {last_name}"
            
            if full_name in self._full_name_to_learner:
                return self._full_name_to_learner[full_name]
        
        # Try partial matching
        words = text_lower.split()
        for i, word in enumerate(words):
            if word in self._name_to_learner:
                # Check if next word could be surname
                learners = self._name_to_learner[word]
                if i + 1 < len(words):
                    potential_surname = words[i + 1]
                    for learner in learners:
                        if learner['surname'].lower() == potential_surname:
                            return {
                                'acc_no': learner['acc_no'],
                                'name': word.capitalize(),
                                'surname': learner['surname'],
                                'grade': learner['grade']
                            }
        
        return None
    
    def _check_signature_in_context(
        self, 
        context_lines: List[Dict],
        image,
        line_info: Dict
    ) -> bool:
        """Check if there's a signature in the context."""
        for ctx_line in context_lines:
            if SIGNATURE_LINE_REGEX.search(ctx_line['text']):
                # Found signature line, check for actual signature pixels
                return self._detect_signature_pixels(image, ctx_line['box'])
        return False
    
    def _detect_signature_pixels(self, image, box) -> bool:
        """Detect if there are signature pixels in the area."""
        try:
            from PIL import Image
            
            # Get bounding box coordinates
            x_coords = [p[0] for p in box]
            y_coords = [p[1] for p in box]
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            
            # Crop the signature area
            signature_area = image.crop((min_x, min_y, max_x, max_y))
            
            # Convert to grayscale and check for dark pixels
            gray = signature_area.convert('L')
            pixels = list(gray.getdata())
            
            # Count dark pixels (signature ink)
            dark_count = sum(1 for p in pixels if p < 150)
            
            # If more than 5% of pixels are dark, consider it signed
            threshold = len(pixels) * 0.05
            return dark_count > threshold
            
        except Exception as e:
            self.logger.error(f"Error detecting signature: {e}")
            return False
    
    def _get_context_around_block(self, blocks, target_block) -> str:
        """Get text context around a block."""
        context_parts = []
        try:
            target_index = blocks.index(target_block)
            start_index = max(0, target_index - 2)
            end_index = min(len(blocks), target_index + 3)
            
            for i in range(start_index, end_index):
                if blocks[i][6] == 0:  # Text block
                    context_parts.append(blocks[i][4].strip())
        except (ValueError, IndexError):
            pass
        
        return ' '.join(context_parts)
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse a date string into a date object."""
        # Try different date formats
        formats = [
            '%Y-%m-%d',
            '%d-%m-%Y',
            '%d/%m/%Y',
            '%Y/%m/%d',
            '%d.%m.%Y',
            '%Y.%m.%d'
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue
        
        return None
    
    def _initialize_ocr_reader(self):
        """Initialize the OCR reader (lazy loading)."""
        try:
            import easyocr
            
            self.logger.info("Initializing EasyOCR reader...")
            reader = easyocr.Reader(['en'], gpu=False)
            self.logger.info("EasyOCR reader initialized successfully")
            return reader
            
        except ImportError:
            self.logger.warning("EasyOCR not available. Install with: pip install easyocr")
            return None
        except Exception as e:
            self.logger.error(f"Failed to initialize OCR reader: {e}")
            return None


def create_ocr_processor_from_payment_db(db_manager) -> AttendanceOCRProcessor:
    """
    Create an OCR processor with learner list from the payment system database.
    
    This is a convenience function for integration with the existing payment system.
    
    Args:
        db_manager: The payment system database manager
        
    Returns:
        Configured AttendanceOCRProcessor instance
    """
    try:
        # Fetch learners from payment database
        query = """
            SELECT acc_no, name, surname, grade 
            FROM Learners 
            WHERE is_active = 1
            ORDER BY surname, name
        """
        learners = db_manager.execute_query(query, fetchall=True)
        
        learner_list = []
        if learners:
            for learner in learners:
                learner_list.append({
                    'acc_no': learner[0],
                    'name': learner[1],
                    'surname': learner[2],
                    'grade': learner[3]
                })
        
        return AttendanceOCRProcessor(learner_list=learner_list)
        
    except Exception as e:
        logging.error(f"Error creating OCR processor from payment DB: {e}")
        return AttendanceOCRProcessor()