import os
import easyocr

def setup_local_ocr():
    """Configure EasyOCR to use local app directory for models."""
    # Set up paths
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    models_dir = os.path.join(app_dir, 'resources', 'ocr_models')
    
    # Create models directory if it doesn't exist
    os.makedirs(models_dir, exist_ok=True)
    
    # Configure EasyOCR to use our directory
    os.environ['EASYOCR_MODULE_PATH'] = models_dir
    
    # Initialize reader - this will download models to our directory
    reader = easyocr.Reader(['en'], model_storage_directory=models_dir)
    
    return models_dir