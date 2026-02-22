import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from .video_path_manager import video_path_manager

class QAManager:
    """QA数据管理器，用于处理qa_results.json文件"""
    
    def __init__(self, qa_file_path: str = None):
        # 优先使用环境变量指定的文件路径
        if qa_file_path is None:
            import os
            qa_file_path = os.environ.get('QA_FILE_PATH', 'qa_results.json')
        
        self.qa_file_path = qa_file_path
        self.qa_data = self.load_qa_data()
    
    def load_qa_data(self) -> Dict:
        """加载QA数据"""
        try:
            if os.path.exists(self.qa_file_path):
                with open(self.qa_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # 检查数据格式并转换
                if 'qas' in data and isinstance(data['qas'], list):
                    # 新格式：aria01_214-1_qa_results.json
                    return self._convert_new_format_to_legacy(data)
                else:
                    # 旧格式：qa_results.json
                    return data
            return {}
        except Exception as e:
            print(f"加载QA数据失败: {e}")
            return {}
    
    def _convert_new_format_to_legacy(self, new_data: Dict) -> Dict:
        """将新格式转换为旧格式"""
        legacy_data = {}
        
        # 获取视频信息
        video_name = new_data.get('video_name', 'unknown')
        video_file = new_data.get('video_file', 'unknown.mp4')
        
        # 转换每个QA
        for qa in new_data.get('qas', []):
            segment_id = qa.get('segment_id', 'unknown')
            
            # 如果segment不存在，创建它
            if segment_id not in legacy_data:
                legacy_data[segment_id] = {
                    'state': '待审阅',
                    'last_modify': new_data.get('sync_time', ''),
                    'QAs': []
                }
            
            # 转换QA格式
            legacy_qa = {
                'Question': qa.get('question', ''),
                'Answer': qa.get('answer', ''),
                'Question Type': qa.get('question_type', ''),
                'Temporal Direction': qa.get('temporal_direction', ''),
                'Reason': qa.get('reason', ''),
                'start_time': qa.get('start_time', '00:00'),
                'end_time': qa.get('end_time', '00:10'),
                'cut_point': qa.get('cut_point', '00:05'),
                'cut_points': qa.get('cut_points', []),
                'video_source': video_file,
                '视角': []  # 多视角支持
            }
            
            legacy_data[segment_id]['QAs'].append(legacy_qa)
        
        return legacy_data
    
    def save_qa_data(self) -> bool:
        """保存QA数据"""
        try:
            with open(self.qa_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.qa_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存QA数据失败: {e}")
            return False
    
    def get_all_segments(self) -> List[Dict]:
        """获取所有segment信息"""
        segments = []
        for segment_id, segment_data in self.qa_data.items():
            # 确保segment_data是字典类型
            if not isinstance(segment_data, dict):
                print(f"警告: segment_data不是字典类型: {type(segment_data)}")
                continue
                
            segment_info = {
                'id': segment_id,
                'state': segment_data.get('state', ''),
                'last_modify': segment_data.get('last_modify', ''),
                'qa_count': len(segment_data.get('QAs', [])),
                'video_source': self._extract_video_source(segment_id),
                'start_time': self._extract_start_time(segment_id),
                'end_time': self._extract_end_time(segment_id)
            }
            segments.append(segment_info)
        return segments
    
    def get_segment_qas(self, segment_id: str) -> List[Dict]:
        """获取指定segment的所有QA"""
        if segment_id not in self.qa_data:
            return []
        
        segment_data = self.qa_data[segment_id]
        qas = segment_data.get('QAs', [])
        
        # 为每个QA添加额外信息
        enhanced_qas = []
        for i, qa in enumerate(qas):
            enhanced_qa = qa.copy()
            enhanced_qa['qa_id'] = f"{segment_id}_qa_{i}"
            enhanced_qa['video_source'] = self._extract_video_source(segment_id)
            enhanced_qa['start_time'] = self._extract_start_time(segment_id)
            enhanced_qa['end_time'] = self._extract_end_time(segment_id)
            enhanced_qa['cut_point'] = self._extract_cut_point(segment_id)
            enhanced_qa['segment_id'] = segment_id
            
            # 添加多视角支持
            if '视角' not in enhanced_qa:
                enhanced_qa['视角'] = []
            
            # 确保时间格式为MM:SS
            enhanced_qa['start_time'] = self._format_time_to_mm_ss(enhanced_qa['start_time'])
            enhanced_qa['end_time'] = self._format_time_to_mm_ss(enhanced_qa['end_time'])
            enhanced_qa['cut_point'] = self._format_time_to_mm_ss(enhanced_qa['cut_point'])
            
            # 添加动态视频路径
            enhanced_qa['video_path'] = self._get_dynamic_video_path(enhanced_qa)
            
            enhanced_qas.append(enhanced_qa)
        
        return enhanced_qas
    
    def update_qa(self, qa_id: str, updated_data: Dict) -> bool:
        """更新QA信息"""
        try:
            # 解析qa_id获取segment_id和qa_index
            parts = qa_id.split('_qa_')
            if len(parts) != 2:
                return False
            
            segment_id = parts[0]
            qa_index = int(parts[1])
            
            if segment_id not in self.qa_data:
                return False
            
            qas = self.qa_data[segment_id].get('QAs', [])
            if qa_index >= len(qas):
                return False
            
            # 更新QA数据
            for key, value in updated_data.items():
                if key in qas[qa_index]:
                    qas[qa_index][key] = value
            
            # 更新最后修改时间
            self.qa_data[segment_id]['last_modify'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return self.save_qa_data()
        except Exception as e:
            print(f"更新QA失败: {e}")
            return False
    
    def add_qa(self, segment_id: str, qa_data: Dict) -> bool:
        """添加新的QA"""
        try:
            if segment_id not in self.qa_data:
                return False
            
            if 'QAs' not in self.qa_data[segment_id]:
                self.qa_data[segment_id]['QAs'] = []
            
            # 添加必要的字段
            qa_data['video_source'] = self._extract_video_source(segment_id)
            qa_data['start_time'] = self._extract_start_time(segment_id)
            qa_data['end_time'] = self._extract_end_time(segment_id)
            qa_data['cut_point'] = self._extract_cut_point(segment_id)
            
            self.qa_data[segment_id]['QAs'].append(qa_data)
            self.qa_data[segment_id]['last_modify'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return self.save_qa_data()
        except Exception as e:
            print(f"添加QA失败: {e}")
            return False
    
    def delete_qa(self, qa_id: str) -> bool:
        """删除QA"""
        try:
            # 解析qa_id获取segment_id和qa_index
            parts = qa_id.split('_qa_')
            if len(parts) != 2:
                return False
            
            segment_id = parts[0]
            qa_index = int(parts[1])
            
            if segment_id not in self.qa_data:
                return False
            
            qas = self.qa_data[segment_id].get('QAs', [])
            if qa_index >= len(qas):
                return False
            
            # 删除QA
            del qas[qa_index]
            self.qa_data[segment_id]['last_modify'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            return self.save_qa_data()
        except Exception as e:
            print(f"删除QA失败: {e}")
            return False
    
    def _extract_video_source(self, segment_id: str) -> str:
        """从segment_id提取视频源信息"""
        # segment_id格式: segment_1756255468053_0
        # 其中1756255468053是时间戳，_0是片段索引
        parts = segment_id.split('_')
        if len(parts) >= 3:
            timestamp = parts[1]
            # 将时间戳转换为可读格式
            try:
                import datetime
                dt = datetime.datetime.fromtimestamp(int(timestamp) / 1000)
                return f"video_{dt.strftime('%Y%m%d_%H%M%S')}.mp4"
            except:
                return f"video_{timestamp}.mp4"
        return f"video_{segment_id}.mp4"
    
    def _extract_start_time(self, segment_id: str) -> str:
        """从segment_id提取开始时间"""
        # 从segment_id中提取时间戳，然后计算相对时间
        # 这里假设每个segment大约10秒，实际需要根据数据调整
        parts = segment_id.split('_')
        if len(parts) >= 3:
            try:
                segment_index = int(parts[2])
                start_seconds = segment_index * 10  # 假设每个segment 10秒
                minutes = start_seconds // 60
                seconds = start_seconds % 60
                return f"{minutes:02d}:{seconds:02d}"
            except:
                pass
        return "00:00"
    
    def _extract_end_time(self, segment_id: str) -> str:
        """从segment_id提取结束时间"""
        # 从segment_id中提取时间戳，然后计算相对时间
        parts = segment_id.split('_')
        if len(parts) >= 3:
            try:
                segment_index = int(parts[2])
                end_seconds = (segment_index + 1) * 10  # 假设每个segment 10秒
                minutes = end_seconds // 60
                seconds = end_seconds % 60
                return f"{minutes:02d}:{seconds:02d}"
            except:
                pass
        return "00:10"
    
    def _extract_cut_point(self, segment_id: str) -> str:
        """从segment_id提取切分点"""
        # 切分点通常是segment的中间时间
        parts = segment_id.split('_')
        if len(parts) >= 3:
            try:
                segment_index = int(parts[2])
                cut_seconds = segment_index * 10 + 5  # 中间点
                minutes = cut_seconds // 60
                seconds = cut_seconds % 60
                return f"{minutes:02d}:{seconds:02d}"
            except:
                pass
        return "00:05"
    
    def _format_time_to_mm_ss(self, time_str: str) -> str:
        """将时间格式转换为MM:SS"""
        if not time_str:
            return "00:00"
        
        # 如果已经是MM:SS格式，直接返回
        if ':' in time_str and '.' not in time_str:
            return time_str
        
        # 如果是MM:SS.ss格式，去掉小数部分
        if '.' in time_str:
            return time_str.split('.')[0]
        
        # 如果是纯数字，转换为MM:SS
        try:
            seconds = int(time_str)
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes:02d}:{secs:02d}"
        except:
            return time_str
    
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
    
    def get_qa_statistics(self) -> Dict:
        """获取QA统计信息"""
        total_segments = len(self.qa_data)
        total_qas = sum(len(segment_data.get('QAs', [])) for segment_data in self.qa_data.values())
        
        # 按问题类型统计
        question_types = {}
        for segment_data in self.qa_data.values():
            for qa in segment_data.get('QAs', []):
                q_type = qa.get('Question Type', 'Unknown')
                question_types[q_type] = question_types.get(q_type, 0) + 1
        
        return {
            'total_segments': total_segments,
            'total_qas': total_qas,
            'question_types': question_types
        }
    
    def _get_dynamic_video_path(self, qa: Dict) -> Optional[str]:
        """
        根据QA信息获取动态视频路径
        
        Args:
            qa: QA数据字典
            
        Returns:
            str: 视频文件的相对路径，如果找不到返回None
        """
        # 从QA中提取video_name和视角信息
        video_name = qa.get('video_source', '').replace('.mp4', '')
        perspectives = qa.get('视角', [])
        
        # 如果视角列表不为空，使用第一个视角
        perspective = perspectives[0] if perspectives else None
        
        # 使用视频路径管理器查找视频文件
        return video_path_manager.get_web_video_path(video_name, perspective)
    
    def set_video_base_directory(self, video_dir: str):
        """设置视频基础目录"""
        video_path_manager.set_base_video_dir(video_dir)
    
    def get_video_info_for_segment(self, segment_id: str) -> Dict:
        """
        获取segment的视频信息
        
        Args:
            segment_id: segment ID
            
        Returns:
            Dict: 视频信息
        """
        if segment_id not in self.qa_data:
            return {}
        
        segment_data = self.qa_data[segment_id]
        qas = segment_data.get('QAs', [])
        
        if not qas:
            return {}
        
        # 从第一个QA获取视频信息
        first_qa = qas[0]
        video_name = first_qa.get('video_source', '').replace('.mp4', '')
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
