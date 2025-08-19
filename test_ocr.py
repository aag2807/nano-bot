#!/usr/bin/env python3
"""
Test script for OCR functionality in NANO Banking Assistant
"""

import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from nano.tools.ocr import OCRTools
from app.database import get_db
import tempfile
from PIL import Image, ImageDraw, ImageFont


def create_test_check_image():
    """Create a simple test check image for OCR testing."""
    # Create a simple check image
    img = Image.new('RGB', (800, 300), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use a default font, fallback to basic if not available
    try:
        font = ImageFont.truetype("arial.ttf", 16)
        small_font = ImageFont.truetype("arial.ttf", 12)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Draw check elements
    draw.text((50, 20), "Bank Of AI", fill='black', font=font)
    draw.text((600, 20), "Check #: 1001", fill='black', font=font)
    draw.text((50, 60), "Date: 08/18/2025", fill='black', font=font)
    
    draw.text((50, 100), "Pay to the order of: John Smith", fill='black', font=font)
    draw.text((50, 140), "Amount: $1,250.00", fill='black', font=font)
    draw.text((50, 180), "Memo: Rent Payment", fill='black', font=font)
    
    draw.text((50, 220), "Account: 123456789", fill='black', font=small_font)
    draw.text((200, 220), "Routing: 987654321", fill='black', font=small_font)
    
    # Save to temporary file
    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    img.save(temp_file.name)
    return temp_file.name


def test_ocr_engines():
    """Test available OCR engines."""
    print("Testing OCR Engine Availability:")
    print("-" * 40)
    
    try:
        import pytesseract
        print("✓ Tesseract OCR: Available")
        tesseract_available = True
    except ImportError:
        print("✗ Tesseract OCR: Not available")
        tesseract_available = False
    
    try:
        import easyocr
        print("✓ EasyOCR: Available")
        easyocr_available = True
    except ImportError:
        print("✗ EasyOCR: Not available")
        easyocr_available = False
    
    try:
        import cv2
        print("✓ OpenCV: Available")
    except ImportError:
        print("✗ OpenCV: Not available")
    
    try:
        from PIL import Image
        print("✓ Pillow (PIL): Available")
    except ImportError:
        print("✗ Pillow (PIL): Not available")
    
    return tesseract_available or easyocr_available


def test_ocr_functionality():
    """Test OCR functionality with a sample image."""
    print("\nTesting OCR Functionality:")
    print("-" * 40)
    
    # Create test image
    test_image_path = create_test_check_image()
    print(f"Created test check image: {test_image_path}")
    
    try:
        # Initialize OCR tools (without database for testing)
        class MockDB:
            def add(self, obj): pass
            def commit(self): pass
        
        ocr_tools = OCRTools(MockDB())
        
        # Test image preprocessing
        import cv2
        image = cv2.imread(test_image_path)
        if image is not None:
            processed = ocr_tools._preprocess_image(image)
            print("✓ Image preprocessing: Working")
        else:
            print("✗ Image preprocessing: Failed to load image")
            return False
        
        # Test text extraction (if engines available)
        if ocr_tools.easyocr_available:
            print("Testing EasyOCR...")
            result = ocr_tools._extract_text_from_image(test_image_path, "easyocr", True)
            if result["success"]:
                print(f"✓ EasyOCR extraction successful")
                print(f"  Extracted text: {result['text'][:100]}...")
                print(f"  Confidence: {result.get('confidence', 'N/A')}")
            else:
                print(f"✗ EasyOCR extraction failed: {result.get('message', 'Unknown error')}")
        
        if ocr_tools.tesseract_available:
            print("Testing Tesseract...")
            result = ocr_tools._extract_text_from_image(test_image_path, "tesseract", True)
            if result["success"]:
                print(f"✓ Tesseract extraction successful")
                print(f"  Extracted text: {result['text'][:100]}...")
            else:
                print(f"✗ Tesseract extraction failed: {result.get('message', 'Unknown error')}")
        
        # Test banking document analysis
        sample_text = "Bank Of AI Check #: 1001 Date: 08/18/2025 Pay to the order of: John Smith Amount: $1,250.00 Account: 123456789 Routing: 987654321"
        analysis = ocr_tools._analyze_banking_document(sample_text)
        print(f"✓ Banking document analysis: {analysis['document_type']}")
        print(f"  Found account numbers: {analysis['account_numbers']}")
        print(f"  Found amounts: {analysis['amounts']}")
        
        return True
        
    except Exception as e:
        print(f"✗ OCR functionality test failed: {str(e)}")
        return False
    
    finally:
        # Clean up test image
        try:
            os.unlink(test_image_path)
        except:
            pass


def main():
    """Main test function."""
    print("NANO Banking Assistant - OCR Test Suite")
    print("=" * 50)
    
    # Test engine availability
    engines_available = test_ocr_engines()
    
    if not engines_available:
        print("\n❌ No OCR engines available!")
        print("Please install OCR dependencies:")
        print("  pip install -r requirements-ocr.txt")
        print("\nFor Tesseract, also install the binary:")
        print("  Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
        print("  macOS: brew install tesseract")
        print("  Ubuntu: sudo apt install tesseract-ocr")
        return False
    
    # Test functionality
    functionality_works = test_ocr_functionality()
    
    print("\n" + "=" * 50)
    if functionality_works:
        print("✅ OCR functionality is working correctly!")
        print("Your NANO assistant is ready to process documents.")
    else:
        print("❌ OCR functionality has issues.")
        print("Please check the error messages above and ensure all dependencies are installed.")
    
    return functionality_works


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)