# 自动翻译工作流说明

## 原理
该系统通过 SSH 隧道连接远程服务器上的 Ollama (DeepSeek/Qwen) 模型，自动将网站中的 `.qmd` 文章翻译成另一种语言（中 <-> 英）。

## 核心逻辑
1. **源文件**：你撰写的 `index.qmd`。
   - 如果 `lang: en` -> 脚本生成 `index.zh.qmd` (中文版)。
   - 如果 `lang: zh` -> 脚本生成 `index.en.qmd` (英文版)。
2. **防覆盖**：如果目标文件（如 `index.zh.qmd`）已存在，脚本**跳过**，绝不覆盖。这意味着你可以自由修改 AI 生成的草稿。
3. **前端**：网页右下角的悬浮按钮会根据当前文件名自动判断跳转目标。

## 使用步骤

### 1. 准备 SSH 隧道
在本地终端（Local Terminal）运行：
```bash
# 将远程服务器 (43.142.67.102) 的 Ollama (11434) 映射到本地 11435
ssh -N -L 11435:localhost:11434 -p 6000 chance@43.142.67.102
```
*输入密码后，终端会卡住，保持开启即可。*

### 2. 运行翻译脚本
在 Cursor 终端运行：
```bash
./venv/bin/python scripts/translate_site.py
```
脚本会自动扫描所有 `.qmd`，补充缺失的翻译版本。

### 3. 预览
```bash
quarto preview
```

## 注意事项
1. **必须标注语言**：确保你的 `.qmd` 头部包含 `lang: en` 或 `lang: zh`。
2. **强制重翻**：如果对 AI 翻译不满意，直接删除对应的 `.zh.qmd` (或 `.en.qmd`) 文件，再次运行脚本即可。
3. **404 问题**：如果你新增了文章但没运行翻译脚本，网页上的“切换语言”按钮点击后会报 404。请记得每次发文后运行一次脚本。

## 配置
修改 `scripts/translate_site.py`：
- `OLLAMA_BASE_URL`: 默认 `http://127.0.0.1:11435/v1`
- `MODEL_NAME`: 默认 `deepseek-r1:latest` (可改为 `qwen2.5:14b` 等)
