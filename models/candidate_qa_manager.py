#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
候选QA数据管理器
专门处理test_qacandidate_v1.json格式的数据，支持实时自动保存
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from .video_path_manager import video_path_manager

class CandidateQAManager:
    """候选QA数据管理器，用于处理test_qacandidate_v1.json文件"""
    
    def __init__(self, input_file_path: str = 'test_qacandidate_v1.json'):
        self.input_file_path = input_file_path
        # 始终保存到选择的文件，不再区分输入和输出
        self.output_file_path = input_file_path
        self.qa_data = self.load_qa_data()
        self.auto_save_enabled = True
    
    def _get_output_file_path(self, input_file_path: str) -> str:
        """保持与输入文件相同路径（统一单文件工作流）"""
        return input_file_path
    
    def load_qa_data(self) -> Dict:
        """从输入文件加载QA数据"""
        try:
            if os.path.exists(self.input_file_path):
                with open(self.input_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f"成功加载候选QA数据: {len(data)} 个segments")
                print(f"输入文件: {self.input_file_path}")
                print(f"输出文件: {self.output_file_path}")
                return data
            return {}
        except Exception as e:
            print(f"加载QA数据失败: {e}")
            return {}
    
    def get_current_file(self) -> str:
        """获取当前输入文件路径"""
        return self.input_file_path
    
    def get_output_file(self) -> str:
        """获取当前输出文件路径"""
        return self.output_file_path
    
    def update_segment_status(self, segment_id: str, new_status: str) -> bool:
        """更新segment状态"""
        try:
            if segment_id not in self.qa_data:
                return False
            
            self.qa_data[segment_id]['state'] = new_status
            self.qa_data[segment_id]['last_modify'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return self.save_qa_data()
        except Exception as e:
            print(f"更新segment状态失败: {e}")
            return False
    
    def save_qa_data(self) -> bool:
        """保存QA数据到输出文件"""
        try:
            # 如有目录部分则确保存在；若无目录则直接写到当前工作目录
            dir_path = os.path.dirname(self.output_file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            with open(self.output_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.qa_data, f, ensure_ascii=False, indent=2)
            print(f"QA数据已保存到: {self.output_file_path}")
            return True
        except Exception as e:
            print(f"保存QA数据失败: {e}")
            return False
    
    def auto_save(self):
        """自动保存（如果启用）"""
        if self.auto_save_enabled:
            self.save_qa_data()
    
    def get_all_segments(self) -> List[Dict]:
        """获取所有segment信息"""
        segments = []
        for segment_id, segment_data in self.qa_data.items():
            segment_info = {
                'id': segment_id,
                'video_name': segment_data.get('video_name', ''),
                'sync_time': segment_data.get('sync_time', ''),
                'total_qas': segment_data.get('total_qas', 0),
                'qa_count': len(segment_data.get('qas', [])),
                'qas': segment_data.get('qas', []),  # 包含QA数据以便计算时间范围
                'state': segment_data.get('state', 'unavailable'),
                'last_modify': segment_data.get('last_modify', '')
            }
            segments.append(segment_info)
        return segments
    
    def get_segment_qas(self, segment_id: str) -> List[Dict]:
        """获取指定segment的所有QA"""
        if segment_id not in self.qa_data:
            return []
        
        segment_data = self.qa_data[segment_id]
        qas = segment_data.get('qas', [])
        
        # 为每个QA添加视频路径信息
        enhanced_qas = []
        for qa in qas:
            enhanced_qa = qa.copy()
            
            # 添加视频路径
            video_name = segment_data.get('video_name', '')
            perspectives = qa.get('视角', [])
            perspective = perspectives[0] if perspectives else None
            
            enhanced_qa['video_path'] = video_path_manager.get_web_video_path(video_name, perspective)
            enhanced_qas.append(enhanced_qa)
        
        return enhanced_qas
    
    def update_qa(self, qa_id: str, updated_data: Dict) -> bool:
        """更新QA信息并自动保存"""
        try:
            # 解析qa_id获取segment_id
            parts = qa_id.split('_qa_')
            if len(parts) != 2:
                return False
            
            segment_id = parts[0]
            qa_index = int(parts[1])
            
            if segment_id not in self.qa_data:
                return False
            
            qas = self.qa_data[segment_id].get('qas', [])
            if qa_index >= len(qas):
                return False
            
            # 更新QA数据（过滤掉不应该保存的字段）
            excluded_fields = {'video_path'}  # 不应该保存到JSON文件中的字段
            for key, value in updated_data.items():
                if key not in excluded_fields:
                    qas[qa_index][key] = value
            
            # 更新sync_time
            self.qa_data[segment_id]['sync_time'] = datetime.now().isoformat() + 'Z'
            
            # 自动保存
            self.auto_save()
            
            return True
        except Exception as e:
            print(f"更新QA失败: {e}")
            return False
    
    def add_qa(self, segment_id: str, qa_data: Dict) -> bool:
        """添加新的QA并自动保存"""
        try:
            if segment_id not in self.qa_data:
                return False
            
            if 'qas' not in self.qa_data[segment_id]:
                self.qa_data[segment_id]['qas'] = []
            
            # 生成qa_id
            qa_count = len(self.qa_data[segment_id]['qas'])
            qa_data['qa_id'] = f"{segment_id}_qa_{qa_count}"
            qa_data['segment_id'] = segment_id
            
            # 过滤掉不应该保存的字段
            excluded_fields = {'video_path'}  # 不应该保存到JSON文件中的字段
            filtered_qa_data = {k: v for k, v in qa_data.items() if k not in excluded_fields}
            
            # 添加QA
            self.qa_data[segment_id]['qas'].append(filtered_qa_data)
            
            # 更新total_qas
            self.qa_data[segment_id]['total_qas'] = len(self.qa_data[segment_id]['qas'])
            
            # 更新sync_time
            self.qa_data[segment_id]['sync_time'] = datetime.now().isoformat() + 'Z'
            
            # 自动保存
            self.auto_save()
            
            return True
        except Exception as e:
            print(f"添加QA失败: {e}")
            return False
    
    def delete_qa(self, qa_id: str) -> bool:
        """删除QA并自动保存"""
        try:
            # 解析qa_id获取segment_id和qa_index
            parts = qa_id.split('_qa_')
            if len(parts) != 2:
                return False
            
            segment_id = parts[0]
            qa_index = int(parts[1])
            
            if segment_id not in self.qa_data:
                return False
            
            qas = self.qa_data[segment_id].get('qas', [])
            if qa_index >= len(qas):
                return False
            
            # 删除QA
            del qas[qa_index]
            
            # 重新编号剩余的QA
            for i, qa in enumerate(qas):
                qa['qa_id'] = f"{segment_id}_qa_{i}"
            
            # 更新total_qas
            self.qa_data[segment_id]['total_qas'] = len(qas)
            
            # 更新sync_time
            self.qa_data[segment_id]['sync_time'] = datetime.now().isoformat() + 'Z'
            
            # 自动保存
            self.auto_save()
            
            return True
        except Exception as e:
            print(f"删除QA失败: {e}")
            return False
    
    def get_video_info_for_segment(self, segment_id: str) -> Dict:
        """获取segment的视频信息"""
        if segment_id not in self.qa_data:
            return {}
        
        segment_data = self.qa_data[segment_id]
        video_name = segment_data.get('video_name', '')
        qas = segment_data.get('qas', [])
        
        if not qas:
            return {}
        
        # 从第一个QA获取视角信息
        first_qa = qas[0]
        perspectives = first_qa.get('视角', [])
        
        # 获取视频详细信息
        video_info = video_path_manager.get_video_info(video_name)
        if not video_info:
            return {}
        
        return {
            'video_name': video_name,
            'video_type': video_info.get('type', 'unknown'),
            'available_perspectives': video_info.get('files', []),
            'current_perspective': perspectives[0] if perspectives else None,
            'video_path': video_path_manager.get_web_video_path(video_name, perspectives[0] if perspectives else None)
        }
    
    def get_qa_statistics(self) -> Dict:
        """获取QA统计信息"""
        total_segments = len(self.qa_data)
        total_qas = sum(len(segment_data.get('qas', [])) for segment_data in self.qa_data.values())
        
        # 按问题类型统计
        question_types = {}
        for segment_data in self.qa_data.values():
            for qa in segment_data.get('qas', []):
                q_type = qa.get('question_type', 'Unknown')
                question_types[q_type] = question_types.get(q_type, 0) + 1
        
        return {
            'total_segments': total_segments,
            'total_qas': total_qas,
            'question_types': question_types
        }
    
    def set_video_base_directory(self, video_dir: str):
        """设置视频基础目录"""
        video_path_manager.set_base_video_dir(video_dir)
    
    def enable_auto_save(self, enabled: bool = True):
        """启用或禁用自动保存"""
        self.auto_save_enabled = enabled
        print(f"自动保存已{'启用' if enabled else '禁用'}")
    
    def export_final_results(self) -> bool:
        """导出最终结果（强制保存）"""
        return self.save_qa_data()

# 全局候选QA管理器实例
candidate_qa_manager = CandidateQAManager()
