import zipfile
import os

def extract_zip(source_zip_path, target_directory):
    try:
        # Ensure the target directory exists
        if not os.path.exists(target_directory):
            os.makedirs(target_directory)
        
        # Open the ZIP file
        with zipfile.ZipFile(source_zip_path, 'r') as zip_ref:
            # Extract all contents to the target directory
            zip_ref.extractall(target_directory)
            print(f"ZIP file extracted to {target_directory}")
        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        return False

# Example usage:
"""
source_zip_path = 'path/to/your/file.zip'  # Path to the ZIP file
target_directory = 'path/to/extracted/folder'  # Path where you want to extract the contents
extract_zip(source_zip_path, target_directory)
"""

