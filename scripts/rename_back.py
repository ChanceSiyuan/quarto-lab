import os
import frontmatter

def rename_back(file_path):
    """将 .zh.qmd 改回 .qmd"""
    dir_name = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    
    if base_name.endswith('.zh.qmd'):
        new_name = base_name.replace('.zh.qmd', '.qmd')
        new_path = os.path.join(dir_name, new_name)
        
        # 检查目标是否已存在
        if os.path.exists(new_path):
            print(f"Skipping {file_path} (target {new_path} exists)")
            return
        
        print(f"Renaming {file_path} -> {new_path}")
        os.rename(file_path, new_path)

def main():
    print("🚀 Renaming .zh.qmd back to .qmd...")
    
    ignore_dirs = ['_freeze', '_site', '.git', 'venv', 'site_libs']
    
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            if file.endswith(".zh.qmd"):
                rename_back(os.path.join(root, file))
    
    print("✨ Done!")

if __name__ == "__main__":
    main()
