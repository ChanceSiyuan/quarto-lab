import os
import frontmatter
import re

def is_contains_chinese(string):
    """判断字符串是否包含中文字符"""
    for ch in string:
        if u'\u4e00' <= ch <= u'\u9fff':
            return True
    return False

def detect_language(content):
    # 简单的启发式：如果包含超过 10 个中文字符，认为是中文
    chinese_chars = [ch for ch in content if u'\u4e00' <= ch <= u'\u9fff']
    if len(chinese_chars) > 10:
        return 'zh'
    return 'en'

def fix_lang_attribute(file_path):
    try:
        post = frontmatter.load(file_path)
        content = post.content
        
        # 检测真实语言
        detected_lang = detect_language(content)
        current_lang = post.metadata.get('lang')
        
        # 如果当前没有 lang，或者 lang 与检测结果不符
        if current_lang != detected_lang:
            print(f"Fixing {file_path}: {current_lang} -> {detected_lang}")
            
            post.metadata['lang'] = detected_lang
            
            # 写回文件
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(frontmatter.dumps(post))
                
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

def main():
    print("🚀 Starting language detection and fix...")
    
    ignore_dirs = ['_freeze', '_site', '.git', 'venv', 'site_libs']
    
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            if file.endswith(".qmd") and not file.endswith(".zh.qmd") and not file.endswith(".en.qmd"):
                fix_lang_attribute(os.path.join(root, file))
    
    print("✨ Done!")

if __name__ == "__main__":
    main()
