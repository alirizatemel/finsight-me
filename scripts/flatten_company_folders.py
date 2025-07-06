import os
import shutil

base_dir = "data/companies"

for folder in os.listdir(base_dir):
    folder_path = os.path.join(base_dir, folder)
    
    # Sadece klasörlerle ilgileniyoruz
    if os.path.isdir(folder_path):
        expected_filename = f"{folder} (TRY).xlsx"
        src_file = os.path.join(folder_path, expected_filename)
        dest_file = os.path.join(base_dir, expected_filename)

        if os.path.exists(src_file):
            print(f"Moving: {src_file} → {dest_file}")
            shutil.move(src_file, dest_file)
            
            # Klasör boş kaldıysa sil
            try:
                os.rmdir(folder_path)
                print(f"Removed empty folder: {folder_path}")
            except OSError:
                print(f"Folder not empty, skipped removal: {folder_path}")
        else:
            print(f"File not found: {src_file}")
