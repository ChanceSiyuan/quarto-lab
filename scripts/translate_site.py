import os
import re
import frontmatter
from openai import OpenAI

# ================= 配置区域 =================
OLLAMA_BASE_URL = "http://127.0.0.1:11435/v1"
OLLAMA_API_KEY = "ollama" 
MODEL_NAME = "qwen2.5:14b"    

USE_AI_TRANSLATION = True

# 每个 chunk 的最大字符数（防止过长）
MAX_CHUNK_SIZE = 2000

# 需要忽略的目录
IGNORE_DIRS = ['_freeze', '_site', '.git', 'venv', 'site_libs']
# ===========================================

def split_into_chunks(content):
    """
    将 markdown 内容按标题分割成 chunks。
    保留标题作为 chunk 的一部分。
    """
    # 按 ## 或 ### 标题分割，但保留分隔符
    pattern = r'(^#{1,3}\s+.+$)'
    parts = re.split(pattern, content, flags=re.MULTILINE)
    
    chunks = []
    current_chunk = ""
    
    for part in parts:
        if not part.strip():
            continue
        
        # 如果是标题，开始新的 chunk
        if re.match(r'^#{1,3}\s+', part):
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            current_chunk = part + "\n"
        else:
            current_chunk += part
            
            # 如果当前 chunk 太长，强制分割
            if len(current_chunk) > MAX_CHUNK_SIZE:
                chunks.append(current_chunk.strip())
                current_chunk = ""
    
    # 添加最后一个 chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # 如果没有分割成功（比如文章没有标题），返回整个内容作为单个 chunk
    if not chunks:
        chunks = [content]
    
    return chunks

def translate_chunk(chunk, target_lang):
    """
    翻译单个 chunk
    """
    if not USE_AI_TRANSLATION:
        return chunk
    
    try:
        client = OpenAI(base_url=OLLAMA_BASE_URL, api_key=OLLAMA_API_KEY)
        
        if target_lang == "English":
            lang_instruction = "The output MUST be entirely in English. Do NOT output any Chinese characters except those inside math blocks or code blocks."
        else:
            lang_instruction = "The output MUST be entirely in Simplified Chinese."

        system_prompt = (
            f"You are a professional academic translator. Translate the following markdown content into {target_lang}. "
            f"{lang_instruction}\n"
            "Rules:\n"
            "1. Keep all math blocks ($...$ and $$...$$) EXACTLY as is.\n"
            "2. Keep all code blocks (```...```) EXACTLY as is.\n"
            "3. Keep all HTML tags EXACTLY as is.\n"
            "4. Only translate the prose/text.\n"
            "5. Output ONLY the translated content. No explanations."
        )
        
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chunk}
            ],
            temperature=0.1
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"  Error translating chunk: {e}")
        return f"[Translation Error: {e}]\n\n{chunk}"

def translate_content(content, target_lang):
    """
    分块翻译长文档
    """
    chunks = split_into_chunks(content)
    
    if len(chunks) == 1:
        print(f"  Single chunk ({len(content)} chars)")
    else:
        print(f"  Split into {len(chunks)} chunks")
    
    translated_chunks = []
    for i, chunk in enumerate(chunks):
        print(f"  Translating chunk {i+1}/{len(chunks)} ({len(chunk)} chars)...")
        translated = translate_chunk(chunk, target_lang)
        translated_chunks.append(translated)
    
    return "\n\n".join(translated_chunks)

def process_file(file_path):
    """
    处理单个文件
    """
    dir_name = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    
    # 确定源语言和目标
    if base_name.endswith('.zh.qmd'):
        target_lang_code = 'en'
        target_name = base_name.replace('.zh.qmd', '.en.qmd')
    elif base_name.endswith('.en.qmd'):
        target_lang_code = 'zh'
        target_name = base_name.replace('.en.qmd', '.zh.qmd')
    else:
        # 普通 .qmd 文件，读取 lang 属性
        try:
            post = frontmatter.load(file_path)
            source_lang = post.metadata.get('lang', 'en')
        except:
            return
        
        if source_lang == 'zh':
            target_lang_code = 'en'
            target_name = base_name.replace('.qmd', '.en.qmd')
        elif source_lang == 'en':
            target_lang_code = 'zh'
            target_name = base_name.replace('.qmd', '.zh.qmd')
        else:
            return
    
    target_path = os.path.join(dir_name, target_name)
    
    # 检查目标是否存在
    if os.path.exists(target_path):
        return
    
    print(f"Translating: {file_path} -> {target_path}")
    
    # 读取源文件
    post = frontmatter.load(file_path)
    
    # 准备新文件的元数据
    new_metadata = post.metadata.copy()
    new_metadata['lang'] = target_lang_code
    
    # 分块翻译内容
    translated_body = translate_content(post.content, "English" if target_lang_code == 'en' else "Chinese")
    
    # 写入新文件
    new_post = frontmatter.Post(translated_body, **new_metadata)
    
    with open(target_path, 'w', encoding='utf-8') as f:
        f.write(frontmatter.dumps(new_post))
    
    print(f"✅ Created {target_path}")

def main():
    print(f"🚀 Starting chunked translation (Model: {MODEL_NAME})...")
    
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            if file.endswith(".qmd"):
                process_file(os.path.join(root, file))
    
    print("✨ Done!")

if __name__ == "__main__":
    main()
