import os
import shutil

def clean_folder_contents(folder_path, keep_files=None):
    if not os.path.exists(folder_path):
        print(f"Folder does not exist: {folder_path}")
        return
    
    if keep_files is None:
        keep_files = []
        
    print(f"Cleaning contents of: {folder_path}")
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if item in keep_files:
            print(f"  Keeping: {item}")
            continue
            
        try:
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
                print(f"  Deleted folder: {item}")
            else:
                os.remove(item_path)
                print(f"  Deleted file: {item}")
        except Exception as e:
            print(f"  Error deleting {item}: {e}")

def delete_pycache(root_dir):
    print("Searching for __pycache__ folders...")
    for root, dirs, files in os.walk(root_dir):
        for d in dirs:
            if d == '__pycache__':
                pycache_path = os.path.join(root, d)
                try:
                    shutil.rmtree(pycache_path)
                    print(f"  Deleted pycache: {pycache_path}")
                except Exception as e:
                    print(f"  Error deleting pycache {pycache_path}: {e}")

if __name__ == "__main__":
    app_dir = r"C:\Users\HP\pfe\app"
    
    # 1. Clean static/analyses/results/
    results_dir = os.path.join(app_dir, "static", "analyses", "results")
    clean_folder_contents(results_dir)
    
    # 2. Clean outputs/
    outputs_dir = os.path.join(app_dir, "outputs")
    clean_folder_contents(outputs_dir)
    
    # 3. Clean __pycache__ folders
    delete_pycache(app_dir)
    
    print("Cleanup completed successfully!")
