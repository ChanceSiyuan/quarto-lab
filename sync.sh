#!/bin/bash

echo "🚀 开始渲染..."
quarto render

echo "📦 正在同步到服务器..."
# 注意：_site/ 后面有个斜杠，表示同步文件夹里的内容
# -a: 归档模式 (保留时间戳等)
# -v: 显示过程
# -z: 压缩传输
# --delete: 删除服务器上多余的文件（保持与本地完全一致）
rsync -avz --delete -e "ssh -p 6000" _site/ chance@43.142.67.102:/home/chance/docker/quarto-lab/workspace/_site/

echo "✅ 发布完成！"