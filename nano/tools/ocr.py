import os
import uuid
from typing import Dict, List, Optional, Union
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import Document, AuditLog
from app.config import settings
import logging

# OCR libraries
try:
    import pytesseract
    from PIL import Image
    import cv2
    import numpy as np
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

logger = logging.getLogger(__name__)


class OCRTools:
    def __init__(self, db: Session):
        self.db = db
        self.supported_formats = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.pdf']
        
        # Initialize OCR engines
        self.tesseract_available = TESSERACT_AVAILABLE
        self.easyocr_available = EASYOCR_AVAILABLE
        self.easyocr_reader = None
        
        if self.easyocr_available:
            try:
                self.easyocr_reader = easyocr.Reader(['en'])
                logger.info("EasyOCR initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize EasyOCR: {e}")
                self.easyocr_available = False

    def extract_text_from_document(
        self, 
        session_id: str,
        customer_id: str,
        document_id: str,
        ocr_engine: str = "auto",
        preprocessing: bool = True
    ) -> Dict[str, any]:
        """
        Extract text from a customer document using OCR.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID
            document_id: Document ID to process
            ocr_engine: OCR engine to use ("tesseract", "easyocr", "auto")
            preprocessing: Apply image preprocessing for better OCR results
        
        Returns:
            Dict with extracted text and metadata
        """
        try:
            # Verify document exists and belongs to customer
            document = self.db.query(Document).filter(
                Document.document_id == document_id,
                Document.customer_id == customer_id,
                Document.status == "active"
            ).first()

            if not document:
                return {
                    "success": False,
                    "message": "Document not found or access denied"
                }

            # Check if file exists
            if not os.path.exists(document.file_path):
                return {
                    "success": False,
                    "message": "Document file not found on disk"
                }

            # Check if file format is supported
            file_ext = os.path.splitext(document.filename)[1].lower()
            if file_ext not in self.supported_formats:
                return {
                    "success": False,
                    "message": f"File format {file_ext} not supported for OCR. Supported formats: {', '.join(self.supported_formats)}"
                }

            # Determine OCR engine to use
            engine_used = self._select_ocr_engine(ocr_engine)
            if not engine_used:
                return {
                    "success": False,
                    "message": "No OCR engine available. Please install pytesseract or easyocr."
                }

            # Extract text based on file type
            if file_ext == '.pdf':
                extracted_text = self._extract_text_from_pdf(document.file_path, engine_used, preprocessing)
            else:
                extracted_text = self._extract_text_from_image(document.file_path, engine_used, preprocessing)

            if not extracted_text["success"]:
                return extracted_text

            # Analyze extracted text for banking-specific information
            analysis = self._analyze_banking_document(extracted_text["text"])

            # Log successful OCR operation
            self._log_audit(session_id, customer_id, "extract_text_from_document", 
                          f"OCR completed on {document.filename} using {engine_used}", "success")

            return {
                "success": True,
                "document_id": document_id,
                "filename": document.filename,
                "extracted_text": extracted_text["text"],
                "text_length": len(extracted_text["text"]),
                "ocr_engine": engine_used,
                "confidence": extracted_text.get("confidence", "unknown"),
                "document_analysis": analysis,
                "processing_time": extracted_text.get("processing_time", 0)
            }

        except Exception as e:
            self._log_audit(session_id, customer_id, "extract_text_from_document", 
                          f"Error: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"OCR processing failed: {str(e)}"
            }

    def process_uploaded_document_ocr(
        self, 
        session_id: str,
        customer_id: str,
        file_content: bytes,
        filename: str,
        auto_extract: bool = True
    ) -> Dict[str, any]:
        """
        Process uploaded document with automatic OCR extraction.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID
            file_content: File content as bytes
            filename: Original filename
            auto_extract: Automatically extract text after upload
        
        Returns:
            Dict with upload status and OCR results
        """
        try:
            # First, upload the document using existing file tools
            from nano.tools.files import get_file_tools
            file_tools = get_file_tools(self.db)
            
            upload_result = file_tools.upload_document(
                session_id, customer_id, file_content, filename, "identification"
            )
            
            if not upload_result["success"]:
                return upload_result

            document_id = upload_result["document_id"]
            
            # If auto_extract is enabled and file is suitable for OCR
            ocr_result = None
            if auto_extract:
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext in self.supported_formats:
                    ocr_result = self.extract_text_from_document(
                        session_id, customer_id, document_id
                    )

            return {
                "success": True,
                "message": "Document uploaded successfully" + (" and text extracted" if ocr_result and ocr_result["success"] else ""),
                "document_id": document_id,
                "filename": filename,
                "upload_result": upload_result,
                "ocr_result": ocr_result
            }

        except Exception as e:
            self._log_audit(session_id, customer_id, "process_uploaded_document_ocr", 
                          f"Error: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Document processing failed: {str(e)}"
            }

    def extract_banking_information(
        self, 
        session_id: str,
        customer_id: str,
        document_id: str,
        info_type: str = "general"
    ) -> Dict[str, any]:
        """
        Extract specific banking information from document text.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID
            document_id: Document ID to analyze
            info_type: Type of information to extract ("account", "check", "statement", "general")
        
        Returns:
            Dict with extracted banking information
        """
        try:
            # First extract text from document
            ocr_result = self.extract_text_from_document(session_id, customer_id, document_id)
            
            if not ocr_result["success"]:
                return ocr_result

            text = ocr_result["extracted_text"]
            
            # Extract specific banking information based on type
            if info_type == "account":
                extracted_info = self._extract_account_information(text)
            elif info_type == "check":
                extracted_info = self._extract_check_information(text)
            elif info_type == "statement":
                extracted_info = self._extract_statement_information(text)
            else:
                extracted_info = self._analyze_banking_document(text)

            self._log_audit(session_id, customer_id, "extract_banking_information", 
                          f"Extracted {info_type} information from document", "success")

            return {
                "success": True,
                "document_id": document_id,
                "info_type": info_type,
                "extracted_text": text,
                "banking_information": extracted_info,
                "ocr_metadata": {
                    "engine": ocr_result["ocr_engine"],
                    "confidence": ocr_result["confidence"]
                }
            }

        except Exception as e:
            self._log_audit(session_id, customer_id, "extract_banking_information", 
                          f"Error: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Information extraction failed: {str(e)}"
            }

    def _select_ocr_engine(self, preference: str) -> Optional[str]:
        """Select the best available OCR engine."""
        if preference == "tesseract" and self.tesseract_available:
            return "tesseract"
        elif preference == "easyocr" and self.easyocr_available:
            return "easyocr"
        elif preference == "auto":
            # Prefer EasyOCR for better accuracy, fallback to Tesseract
            if self.easyocr_available:
                return "easyocr"
            elif self.tesseract_available:
                return "tesseract"
        
        return None

    def _extract_text_from_image(self, image_path: str, engine: str, preprocessing: bool) -> Dict[str, any]:
        """Extract text from image file."""
        try:
            start_time = datetime.utcnow()
            
            # Load and preprocess image
            image = cv2.imread(image_path)
            if image is None:
                return {"success": False, "message": "Could not load image file"}

            if preprocessing:
                image = self._preprocess_image(image)

            # Extract text based on engine
            if engine == "easyocr":
                results = self.easyocr_reader.readtext(image)
                text = " ".join([result[1] for result in results])
                confidence = np.mean([result[2] for result in results]) if results else 0
            else:  # tesseract
                pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                text = pytesseract.image_to_string(pil_image)
                confidence = "unknown"

            processing_time = (datetime.utcnow() - start_time).total_seconds()

            return {
                "success": True,
                "text": text.strip(),
                "confidence": confidence,
                "processing_time": processing_time
            }

        except Exception as e:
            return {"success": False, "message": f"Image OCR failed: {str(e)}"}

    def _extract_text_from_pdf(self, pdf_path: str, engine: str, preprocessing: bool) -> Dict[str, any]:
        """Extract text from PDF file."""
        try:
            import fitz  # PyMuPDF
            
            start_time = datetime.utcnow()
            doc = fitz.open(pdf_path)
            all_text = ""
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                
                # Try text extraction first
                page_text = page.get_text()
                if page_text.strip():
                    all_text += page_text + "\n"
                else:
                    # If no text, use OCR on page image
                    pix = page.get_pixmap()
                    img_data = pix.tobytes("png")
                    
                    # Convert to OpenCV format for OCR
                    nparr = np.frombuffer(img_data, np.uint8)
                    image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if preprocessing:
                        image = self._preprocess_image(image)
                    
                    if engine == "easyocr":
                        results = self.easyocr_reader.readtext(image)
                        page_text = " ".join([result[1] for result in results])
                    else:
                        pil_image = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
                        page_text = pytesseract.image_to_string(pil_image)
                    
                    all_text += page_text + "\n"
            
            doc.close()
            processing_time = (datetime.utcnow() - start_time).total_seconds()

            return {
                "success": True,
                "text": all_text.strip(),
                "confidence": "mixed",
                "processing_time": processing_time
            }

        except Exception as e:
            return {"success": False, "message": f"PDF OCR failed: {str(e)}"}

    def _preprocess_image(self, image):
        """Apply preprocessing to improve OCR accuracy."""
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply Gaussian blur to reduce noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Apply threshold to get binary image
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Morphological operations to clean up
        kernel = np.ones((1, 1), np.uint8)
        processed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        return processed

    def _analyze_banking_document(self, text: str) -> Dict[str, any]:
        """Analyze text for banking-specific information."""
        import re
        
        analysis = {
            "document_type": "unknown",
            "account_numbers": [],
            "routing_numbers": [],
            "amounts": [],
            "dates": [],
            "names": [],
            "addresses": []
        }
        
        # Account number patterns (6-17 digits)
        account_pattern = r'\b\d{6,17}\b'
        analysis["account_numbers"] = list(set(re.findall(account_pattern, text)))
        
        # Routing number patterns (9 digits)
        routing_pattern = r'\b\d{9}\b'
        analysis["routing_numbers"] = list(set(re.findall(routing_pattern, text)))
        
        # Currency amounts
        amount_pattern = r'\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?'
        analysis["amounts"] = re.findall(amount_pattern, text)
        
        # Date patterns
        date_pattern = r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b'
        analysis["dates"] = re.findall(date_pattern, text)
        
        # Determine document type based on keywords
        text_lower = text.lower()
        if any(word in text_lower for word in ['statement', 'balance', 'transaction']):
            analysis["document_type"] = "bank_statement"
        elif any(word in text_lower for word in ['check', 'pay to', 'memo']):
            analysis["document_type"] = "check"
        elif any(word in text_lower for word in ['application', 'apply', 'loan']):
            analysis["document_type"] = "application"
        elif any(word in text_lower for word in ['id', 'license', 'identification']):
            analysis["document_type"] = "identification"
        
        return analysis

    def _extract_account_information(self, text: str) -> Dict[str, any]:
        """Extract account-specific information."""
        # Implementation for account information extraction
        return self._analyze_banking_document(text)

    def _extract_check_information(self, text: str) -> Dict[str, any]:
        """Extract check-specific information."""
        import re
        
        check_info = {
            "check_number": None,
            "pay_to": None,
            "amount": None,
            "memo": None,
            "date": None
        }
        
        # Check number (usually at top right)
        check_num_pattern = r'(?:check|no\.?)\s*#?\s*(\d+)'
        match = re.search(check_num_pattern, text, re.IGNORECASE)
        if match:
            check_info["check_number"] = match.group(1)
        
        # Pay to the order of
        pay_to_pattern = r'pay\s+to\s+(?:the\s+order\s+of\s+)?(.+?)(?:\$|\n|amount)'
        match = re.search(pay_to_pattern, text, re.IGNORECASE)
        if match:
            check_info["pay_to"] = match.group(1).strip()
        
        return check_info

    def _extract_statement_information(self, text: str) -> Dict[str, any]:
        """Extract statement-specific information."""
        # Implementation for statement information extraction
        analysis = self._analyze_banking_document(text)
        
        # Add statement-specific fields
        analysis["statement_period"] = None
        analysis["beginning_balance"] = None
        analysis["ending_balance"] = None
        analysis["transactions"] = []
        
        return analysis

    def _log_audit(self, session_id: str, customer_id: str, 
                   action: str, details: str, status: str):
        """Log audit trail for OCR operations."""
        try:
            audit_log = AuditLog(
                session_id=session_id,
                customer_id=customer_id,
                action=action,
                details=details,
                status=status,
                timestamp=datetime.utcnow()
            )
            self.db.add(audit_log)
            self.db.commit()
        except Exception as e:
            print(f"Audit logging error: {e}")


def get_ocr_tools(db: Session) -> OCRTools:
    """Factory function to get OCR tools."""
    return OCRTools(db)