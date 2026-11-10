"""人脸库加载与刷新（供 ui.py + face_manager_ui.py 共用）。

抽离自 get_name.py 的模块级逻辑，避免重复实现。

提供：
- DEFAULT_DIR: 默认人脸库目录 (项目根/face_datasets/)
- load_face_library(dir=None) -> (paths, names): 扫描 jpg/png 文件，返回 (路径列表, basename 列表)
- reload_face_library(): 模块内全局缓存重载（供识别热生效）
- get_face_library_cache() -> (paths, names): 读取当前缓存
"""

from __future__ import annotations

import os
from typing import List, Tuple

# 默认人脸库目录 = 项目根/face_datasets/（与原 get_name.py 保持一致）
DEFAULT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_datasets")
SUPPORTED_EXTS = (".jpg", ".jpeg", ".png")

# 模块内全局缓存，供 ui.py 在运行时热重载
_cache_paths: List[str] = []
_cache_names: List[str] = []
_cache_dir: str = DEFAULT_DIR


def load_face_library(dir: str | None = None) -> Tuple[List[str], List[str]]:
    """扫描指定目录下所有人脸图片 (jpg/png)，返回 (路径列表, basename 列表)。

    与原 get_name.py L13-21 行为一致：basename = 文件名去掉扩展名。
    """
    target_dir = dir if dir is not None else DEFAULT_DIR
    paths: List[str] = []
    names: List[str] = []
    if not os.path.isdir(target_dir):
        # 人脸库目录不存在时, 返回空列表 (不抛错, 调用方自己处理)
        return paths, names
    for file in sorted(os.listdir(target_dir)):
        if file.lower().endswith(SUPPORTED_EXTS):
            paths.append(os.path.join(target_dir, file))
            names.append(os.path.splitext(file)[0])
    return paths, names


def reload_face_library(dir: str | None = None) -> Tuple[List[str], List[str]]:
    """刷新模块内全局缓存, 返回刷新后的 (paths, names)。

    调用方: ui.py 启动时调一次, face_manager_ui.py 点「重载」按钮时调一次。
    """
    global _cache_paths, _cache_names, _cache_dir
    _cache_dir = dir if dir is not None else DEFAULT_DIR
    _cache_paths, _cache_names = load_face_library(_cache_dir)
    return _cache_paths, _cache_names


def get_face_library_cache() -> Tuple[List[str], List[str]]:
    """读取当前缓存 (paths, names)。若尚未 reload, 自动执行一次默认 reload。"""
    if not _cache_paths and not _cache_names:
        reload_face_library()
    return _cache_paths, _cache_names


def get_face_library_dir() -> str:
    return _cache_dir