#!/bin/bash

##############################################################################
# Local Highlight Clipper - Claude Code Skill 安裝腳本
##############################################################################

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }
print_header() { echo ""; echo "========================================"; echo "$1"; echo "========================================"; echo ""; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

main() {
    print_header "Local Highlight Clipper - Claude Code Skill 安裝"

    SKILL_DIR="$HOME/.claude/skills/local-highlight-clipper"
    print_info "目標目錄: $SKILL_DIR"

    if [ -d "$SKILL_DIR" ]; then
        print_warning "Skill 目錄已存在: $SKILL_DIR"
        read -p "是否覆蓋安裝？(y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "安裝已取消"
            exit 0
        fi
        rm -rf "$SKILL_DIR"
    fi

    print_info "建立 Skill 目錄..."
    mkdir -p "$SKILL_DIR"

    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    cp -r "$SCRIPT_DIR"/* "$SKILL_DIR/"

    # 清理不需要的檔案
    rm -rf "$SKILL_DIR/.git" "$SKILL_DIR/venv" "$SKILL_DIR/__pycache__" "$SKILL_DIR/highlight-clips" "$SKILL_DIR/docs"
    print_success "檔案複製完成"

    # 檢查 Python
    print_info "檢查 Python 環境..."
    if ! command_exists python3; then
        print_error "未找到 Python 3，請先安裝 Python 3.8+"
        exit 1
    fi
    print_success "Python 已安裝: $(python3 --version)"

    # 安裝 Python 依賴
    print_info "安裝 Python 依賴..."
    if command_exists pip3; then
        pip3 install -q openai-whisper pysrt
    else
        pip install -q openai-whisper pysrt
    fi
    print_success "Python 依賴安裝完成（openai-whisper、pysrt）"

    # 檢查 Whisper
    print_info "檢查 Whisper..."
    if command_exists whisper; then
        print_success "Whisper 已安裝"
    else
        print_warning "Whisper 命令列工具未安裝"
        print_info "安裝方法: pip install openai-whisper"
    fi

    # 檢查 FFmpeg
    print_header "檢查 FFmpeg（字幕燒錄需要）"

    FFMPEG_FOUND=false
    LIBASS_SUPPORTED=false

    if [ -f "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg" ]; then
        print_success "ffmpeg-full 已安裝（Apple Silicon）"
        FFMPEG_FOUND=true
        LIBASS_SUPPORTED=true
    elif [ -f "/usr/local/opt/ffmpeg-full/bin/ffmpeg" ]; then
        print_success "ffmpeg-full 已安裝（Intel Mac）"
        FFMPEG_FOUND=true
        LIBASS_SUPPORTED=true
    elif command_exists ffmpeg; then
        print_success "FFmpeg 已安裝: $(ffmpeg -version | head -n 1)"
        FFMPEG_FOUND=true
        if ffmpeg -filters 2>&1 | grep -q "subtitles"; then
            print_success "FFmpeg 支援 libass（字幕燒錄可用）"
            LIBASS_SUPPORTED=true
        else
            print_warning "FFmpeg 不支援 libass（字幕燒錄不可用）"
        fi
    fi

    if [ "$FFMPEG_FOUND" = false ]; then
        print_error "FFmpeg 未安裝"
        print_info "安裝方法: brew install ffmpeg"
    elif [ "$LIBASS_SUPPORTED" = false ]; then
        print_warning "FFmpeg 缺少 libass 支援，字幕燒錄功能將不可用"
        print_info "macOS 解決方法: brew install ffmpeg-full"
    fi

    print_header "安裝完成！"

    print_success "Local Highlight Clipper 已安裝為 Claude Code Skill"
    echo ""
    print_info "安裝位置: $SKILL_DIR"
    echo ""
    print_info "使用方法："
    print_info "  在 Claude Code 中輸入："
    print_info "  \"幫我把這個直播錄影剪成精華片段：/path/to/video.mp4\""
    echo ""
}

trap 'print_error "安裝過程中發生錯誤"; exit 1' ERR
main
