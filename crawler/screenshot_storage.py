"""
Screenshot storage utilities.
Supports local filesystem storage with S3 migration path.
"""

import os
from django.conf import settings
from urllib.parse import urlparse


class ScreenshotStorage:
    """
    Handles screenshot storage with support for local filesystem and future S3.
    """
    
    def __init__(self):
        self.storage_backend = getattr(settings, 'SCREENSHOT_STORAGE_BACKEND', 'local')
        self.s3_bucket = getattr(settings, 'SCREENSHOT_S3_BUCKET', None)
        self.s3_prefix = getattr(settings, 'SCREENSHOT_S3_PREFIX', 'screenshots/')
    
    def get_screenshot_path(self, url):
        """
        Generate screenshot path from URL.
        
        Args:
            url: The page URL
            
        Returns:
            tuple: (directory_path, filename, relative_path)
        """
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace('www.', '')
        url_path = parsed_url.path.strip('/')
        
        # Build directory structure
        if url_path:
            dir_path = os.path.join(settings.BASE_DIR, 'screenshots', domain, url_path)
            relative_path = os.path.join('screenshots', domain, url_path, 'screenshot.png')
        else:
            dir_path = os.path.join(settings.BASE_DIR, 'screenshots', domain)
            relative_path = os.path.join('screenshots', domain, 'screenshot.png')
        
        return dir_path, 'screenshot.png', relative_path
    
    def save_screenshot(self, filepath, url):
        """
        Save screenshot to storage backend.
        
        Args:
            filepath: Local path to screenshot file
            url: The page URL (used for S3 key generation)
            
        Returns:
            str: Storage path/URL for the screenshot
        """
        if self.storage_backend == 's3':
            return self._save_to_s3(filepath, url)
        else:
            # Already saved locally, just return the path
            return os.path.relpath(filepath, settings.BASE_DIR)
    
    def _save_to_s3(self, filepath, url):
        """
        Upload screenshot to S3.
        
        Args:
            filepath: Local path to screenshot file
            url: The page URL
            
        Returns:
            str: S3 URL or key for the screenshot
        """
        # TODO: Implement S3 upload when needed
        # import boto3
        # s3 = boto3.client('s3')
        # 
        # parsed_url = urlparse(url)
        # domain = parsed_url.netloc.replace('www.', '')
        # url_path = parsed_url.path.strip('/')
        # 
        # if url_path:
        #     s3_key = f"{self.s3_prefix}{domain}/{url_path}/screenshot.png"
        # else:
        #     s3_key = f"{self.s3_prefix}{domain}/screenshot.png"
        # 
        # with open(filepath, 'rb') as f:
        #     s3.upload_fileobj(f, self.s3_bucket, s3_key)
        # 
        # return f"s3://{self.s3_bucket}/{s3_key}"
        
        raise NotImplementedError("S3 storage not yet implemented")
    
    def get_screenshot_url(self, screenshot_path):
        """
        Get the URL to access a screenshot.
        
        Args:
            screenshot_path: The stored screenshot path
            
        Returns:
            str: URL to access the screenshot
        """
        if screenshot_path and screenshot_path.startswith('s3://'):
            # Generate presigned URL for S3
            return self._get_s3_presigned_url(screenshot_path)
        else:
            # Return path for local file (will be served by Django)
            return screenshot_path
    
    def _get_s3_presigned_url(self, s3_path):
        """
        Generate presigned URL for S3 object.
        
        Args:
            s3_path: S3 path (s3://bucket/key)
            
        Returns:
            str: Presigned URL
        """
        # TODO: Implement presigned URL generation
        # import boto3
        # s3 = boto3.client('s3')
        # 
        # # Parse s3://bucket/key
        # parts = s3_path.replace('s3://', '').split('/', 1)
        # bucket = parts[0]
        # key = parts[1] if len(parts) > 1 else ''
        # 
        # return s3.generate_presigned_url(
        #     'get_object',
        #     Params={'Bucket': bucket, 'Key': key},
        #     ExpiresIn=3600  # 1 hour
        # )
        
        raise NotImplementedError("S3 presigned URLs not yet implemented")


# Singleton instance
screenshot_storage = ScreenshotStorage()

