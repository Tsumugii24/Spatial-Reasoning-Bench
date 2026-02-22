#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视频路径管理器
根据video_name和视角属性自动匹配视频文件
"""

import os
import json
from typing import Dict, List, Optional, Tuple
from pathlib import Path

class VideoPathManager:
    """视频路径管理器"""
    
    def __init__(self, base_video_dir: str = None):
        """
        初始化视频路径管理器
        
        Args:
            base_video_dir: 视频文件的基础目录路径
        """
        self.base_video_dir = base_video_dir or "static/videos"
        self.video_cache = {}  # 缓存视频文件信息
        # 严格模式：仅识别 <base>/<video_name>/*.mp4 这种结构
        # 将单文件视为单视角；不再递归 group 层（除非关闭严格模式）
        self.strict_structure = True
        
    def set_base_video_dir(self, video_dir: str):
        """设置视频文件基础目录"""
        self.base_video_dir = video_dir
        self.video_cache.clear()  # 清除缓存
        print(f"视频目录设置为: {video_dir}")

    def set_strict_structure(self, enabled: bool):
        """设置是否启用严格目录结构(<base>/<video_name>/*.mp4)"""
        self.strict_structure = enabled
        self.video_cache.clear()
        print(f"严格目录结构已{'启用' if enabled else '禁用'}")
        
    def scan_video_directory(self) -> Dict[str, Dict]:
        """
        扫描视频目录，建立video_name到文件路径的映射
        
        Returns:
            Dict: {video_name: {type: 'single'|'multi', path: str, files: List[str]}}
        """
        if not os.path.exists(self.base_video_dir):
            print(f"警告: 视频目录不存在: {self.base_video_dir}")
            return {}
            
        video_map = {}
        
        # 遍历基础目录
        for item in os.listdir(self.base_video_dir):
            item_path = os.path.join(self.base_video_dir, item)
            
            if os.path.isfile(item_path) and self._is_video_file(item):
                # 顶层单个视频文件：<base>/<video_name>.ext
                # 严格模式下仍然支持，方便单视角文件逐步迁移
                video_name = os.path.splitext(item)[0]
                video_map[video_name] = {
                    'type': 'single',
                    'path': item_path,
                    'files': [item]
                }
                
            elif os.path.isdir(item_path):
                # 严格模式：仅识别 <base>/<video_name>/*.mp4 结构
                # 目录名即 video_name，目录内所有视频文件为视角文件
                direct_video_files = [f for f in os.listdir(item_path) if self._is_video_file(f)]
                if direct_video_files:
                    video_map[item] = {
                        'type': 'multi',
                        'path': item_path,
                        'files': direct_video_files
                    }

                # 非严格模式下，兼容 group 层：<base>/<group>/<video_name>/<cam*.ext>
                if not self.strict_structure:
                    for sub_item in os.listdir(item_path):
                        sub_item_path = os.path.join(item_path, sub_item)
                        if os.path.isdir(sub_item_path):
                            video_files = [file for file in os.listdir(sub_item_path) if self._is_video_file(file)]
                            if video_files:
                                video_map[sub_item] = {
                                    'type': 'multi',
                                    'path': sub_item_path,
                                    'files': video_files
                                }
                        elif os.path.isfile(sub_item_path) and self._is_video_file(sub_item):
                            video_name = os.path.splitext(sub_item)[0]
                            video_map[video_name] = {
                                'type': 'single',
                                'path': sub_item_path,
                                'files': [sub_item]
                            }
        
        self.video_cache = video_map
        print(f"扫描完成，找到 {len(video_map)} 个视频源")
        return video_map
    
    def find_video_path(self, video_name: str, perspective: str = None) -> Optional[str]:
        """
        根据video_name和视角找到具体的视频文件路径
        
        Args:
            video_name: 视频名称
            perspective: 视角文件名（如 "cam01.mp4"）
            
        Returns:
            str: 视频文件的完整路径，如果找不到返回None
        """
        if not self.video_cache:
            self.scan_video_directory()
        
        if video_name not in self.video_cache:
            print(f"警告: 找不到视频 '{video_name}'")
            return None
        
        video_info = self.video_cache[video_name]
        
        if video_info['type'] == 'single':
            # 单个视频文件
            return video_info['path']
        
        elif video_info['type'] == 'multi':
            # 多视角视频文件夹
            if not perspective:
                print(f"警告: 多视角视频 '{video_name}' 需要指定视角")
                return None
            
            # 在多视角文件夹中查找指定的视角文件
            perspective_path = os.path.join(video_info['path'], perspective)
            if os.path.exists(perspective_path):
                return perspective_path
            else:
                print(f"警告: 在多视角文件夹中找不到视角文件 '{perspective}'")
                # 返回第一个可用的视频文件
                if video_info['files']:
                    first_file = os.path.join(video_info['path'], video_info['files'][0])
                    print(f"使用第一个可用文件: {first_file}")
                    return first_file
                return None
        
        return None
    
    def get_available_perspectives(self, video_name: str) -> List[str]:
        """
        获取指定视频的所有可用视角
        
        Args:
            video_name: 视频名称
            
        Returns:
            List[str]: 可用的视角文件名列表
        """
        if not self.video_cache:
            self.scan_video_directory()
        
        if video_name not in self.video_cache:
            return []
        
        video_info = self.video_cache[video_name]
        return video_info.get('files', [])
    
    def get_video_info(self, video_name: str) -> Optional[Dict]:
        """
        获取视频的详细信息
        
        Args:
            video_name: 视频名称
            
        Returns:
            Dict: 视频信息字典
        """
        if not self.video_cache:
            self.scan_video_directory()
        
        return self.video_cache.get(video_name)
    
    def _is_video_file(self, filename: str) -> bool:
        """检查文件是否为视频文件"""
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
        return any(filename.lower().endswith(ext) for ext in video_extensions)
    
    def get_relative_video_path(self, video_name: str, perspective: str = None) -> Optional[str]:
        """
        获取相对于web根目录的视频路径（用于前端显示）
        
        Args:
            video_name: 视频名称
            perspective: 视角文件名
            
        Returns:
            str: 相对路径，如 "/static/videos/..."
        """
        absolute_path = self.find_video_path(video_name, perspective)
        if not absolute_path:
            return None
        
        # 转换为相对于项目根目录的路径
        project_root = os.path.abspath('.')
        try:
            relative_path = os.path.relpath(absolute_path, project_root)
            # 确保路径使用正斜杠（web标准）
            relative_path = relative_path.replace('\\', '/')
            # 确保路径以 / 开头
            if not relative_path.startswith('/'):
                relative_path = '/' + relative_path
            return relative_path
        except ValueError:
            # 如果无法计算相对路径，返回绝对路径
            return absolute_path
    
    def get_web_video_path(self, video_name: str, perspective: str = None) -> Optional[str]:
        """
        获取用于Web显示的视频路径（包含static/videos前缀）
        
        Args:
            video_name: 视频名称
            perspective: 视角文件名
            
        Returns:
            str: Web路径，如 "/static/videos/..."
        """
        absolute_path = self.find_video_path(video_name, perspective)
        if not absolute_path:
            return None
        
        # 获取相对于项目根目录的路径
        project_root = os.path.abspath('.')
        try:
            relative_path = os.path.relpath(absolute_path, project_root)
            # 确保路径使用正斜杠（web标准）
            relative_path = relative_path.replace('\\', '/')
            # 确保路径以 / 开头
            if not relative_path.startswith('/'):
                relative_path = '/' + relative_path
            return relative_path
        except ValueError:
            # 如果无法计算相对路径，返回绝对路径
            return absolute_path
    
    def list_all_videos(self) -> List[Dict]:
        """
        列出所有可用的视频
        
        Returns:
            List[Dict]: 视频信息列表
        """
        if not self.video_cache:
            self.scan_video_directory()
        
        videos = []
        for video_name, info in self.video_cache.items():
            videos.append({
                'name': video_name,
                'type': info['type'],
                'path': info['path'],
                'files': info['files'],
                'perspectives': info['files'] if info['type'] == 'multi' else []
            })
        
        return videos

# 全局视频路径管理器实例
video_path_manager = VideoPathManager()
