#!/bin/bash
# 自动格式化 Python 文件
# PostToolUse hook for Write|Edit operations

# 读取 stdin 获取工具调用信息
INPUT=$(cat)

# 从 JSON 中提取文件路径（tool_input.file_path）
FILE_PATH=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    # PostToolUse 的输入格式
    tool_input = data.get('tool_input', {})
    print(tool_input.get('file_path', ''))
except:
    pass
" 2>/dev/null)

# 检查是否为 Python 文件
if [[ -z "$FILE_PATH" ]] || [[ ! "$FILE_PATH" == *.py ]]; then
    exit 0
fi

# 检查文件是否存在
if [[ ! -f "$FILE_PATH" ]]; then
    exit 0
fi

# 检查 ruff 是否可用
if ! command -v ruff &> /dev/null; then
    # 尝试使用 uvx
    if command -v uvx &> /dev/null; then
        RUFF_CMD="uvx ruff"
    else
        exit 0
    fi
else
    RUFF_CMD="ruff"
fi

# 执行格式化和检查
$RUFF_CMD format "$FILE_PATH" 2>/dev/null
$RUFF_CMD check --fix "$FILE_PATH" 2>/dev/null

# 静默成功
exit 0
