import os
from pathlib import Path
from file_manager import _generate_thumbnail, SHARED_FOLDER

def regenerate_all_thumbnails():
    print(f"Checking for files in {SHARED_FOLDER}...")
    for item in SHARED_FOLDER.iterdir():
        if item.is_file() and not item.name.startswith('.'):
            print(f"Generating thumbnail for {item.name}...")
            _generate_thumbnail(item)
    print("Done.")

if __name__ == "__main__":
    regenerate_all_thumbnails()
