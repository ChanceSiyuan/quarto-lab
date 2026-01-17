import os
import frontmatter

def rename_by_language(file_path):
    try:
        post = frontmatter.load(file_path)
        lang = post.metadata.get('lang')
        
        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path)
        
        # 只处理 index.qmd 或其他不带语言后缀的文件
        if base_name.endswith('.zh.qmd') or base_name.endswith('.en.qmd'):
            return  # 已经有语言后缀，跳过
        
        if lang == 'zh':
            # 中文 -> 重命名为 .zh.qmd
            new_name = base_name.replace('.qmd', '.zh.qmd')
            new_path = os.path.join(dir_name, new_name)
            print(f"Renaming {file_path} -> {new_path}")
            os.rename(file_path, new_path)
        elif lang == 'en':
            # 英文 -> 保持 .qmd 不变
            print(f"Keeping {file_path} (English)")
        else:
            print(f"Skipping {file_path} (no lang attribute)")
            
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

def main():
    print("🚀 Renaming files by language...")
    
    ignore_dirs = ['_freeze', '_site', '.git', 'venv', 'site_libs']
    
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            if file.endswith(".qmd") and not file.endswith(".zh.qmd") and not file.endswith(".en.qmd"):
                rename_by_language(os.path.join(root, file))
    
    print("✨ Done!")

if __name__ == "__main__":
    main()
