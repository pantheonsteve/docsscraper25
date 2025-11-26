"""
Language detection module for filtering crawled content.
Uses langdetect library for accurate language identification.
"""

import logging
from typing import Optional

logger = logging.getLogger('crawler')

try:
    from langdetect import detect, DetectorFactory
    from langdetect.lang_detect_exception import LangDetectException
    # Set seed for consistent results
    DetectorFactory.seed = 0
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False
    logger.warning("langdetect not installed. Language filtering will be disabled.")


def detect_language(text: str) -> str:
    """
    Detect the language of the given text.
    
    Args:
        text: The text content to analyze
        
    Returns:
        ISO 639-1 language code (e.g., 'en', 'es', 'fr') or 'unknown'
    """
    if not LANGDETECT_AVAILABLE:
        return 'unknown'
    
    if not text or len(text.strip()) < 50:
        # Not enough text to reliably detect language
        return 'unknown'
    
    try:
        # Take a sample from the middle of the text for better accuracy
        # (beginning might have boilerplate, end might have footer content)
        text_length = len(text)
        if text_length > 1000:
            # Use middle section for detection
            start = text_length // 4
            end = start + 1000
            sample = text[start:end]
        else:
            sample = text
        
        detected = detect(sample)
        logger.debug(f"Detected language: {detected} for text sample of {len(sample)} chars")
        return detected
        
    except LangDetectException as e:
        logger.warning(f"Language detection failed: {e}")
        return 'unknown'
    except Exception as e:
        logger.error(f"Unexpected error in language detection: {e}")
        return 'unknown'


def is_english(language_code: str) -> bool:
    """
    Check if the given language code represents English.
    
    Args:
        language_code: ISO 639-1 language code (e.g., 'en', 'es')
        
    Returns:
        True if the language is English, False otherwise
    """
    if language_code == 'unknown':
        # If we can't detect the language, assume it's English to avoid
        # accidentally filtering out pages due to detection failures
        logger.debug("Language unknown, defaulting to English")
        return True
    
    return language_code.lower() in ['en', 'eng']


def get_language_stats(text: str) -> dict:
    """
    Get detailed language detection statistics (for debugging/analysis).
    
    Args:
        text: The text content to analyze
        
    Returns:
        Dictionary with language probabilities
    """
    if not LANGDETECT_AVAILABLE:
        return {'error': 'langdetect not installed'}
    
    if not text or len(text.strip()) < 50:
        return {'error': 'insufficient text'}
    
    try:
        from langdetect import detect_langs
        
        text_length = len(text)
        if text_length > 1000:
            start = text_length // 4
            end = start + 1000
            sample = text[start:end]
        else:
            sample = text
        
        results = detect_langs(sample)
        return {
            'languages': [{'lang': r.lang, 'prob': round(r.prob, 3)} for r in results],
            'sample_length': len(sample)
        }
        
    except Exception as e:
        return {'error': str(e)}
