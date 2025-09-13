import shutil
import os

def copy_folder(source_folder, destination_folder):
    """
    Copies an entire folder (including files and subfolders) to a new location.
    Creates the destination folder if it does not exist.

    Parameters:
        source_folder (str): Path to the source folder.
        destination_folder (str): Path to the destination folder.

    Returns:
        str: Success or error message.
    """
    try:
        if not os.path.exists(source_folder):
            return False
        
        # Create destination folder if it doesn't exist
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)

        # Copy each file and folder manually to avoid errors
        for item in os.listdir(source_folder):
            src_path = os.path.join(source_folder, item)
            dest_path = os.path.join(destination_folder, item)

            if os.path.isdir(src_path):
                shutil.copytree(src_path, dest_path, dirs_exist_ok=True)  # Copy subfolder
            else:
                shutil.copy2(src_path, dest_path)  # Copy file with metadata

        return True
    
    except Exception as e:
        return False

# Example usage:
print(copy_folder("source_folder", "destination_folder"))
