import json
import os
from typing import List, Dict, Optional
from datetime import datetime

class DatasetManager:
    """数据集管理器，负责处理数据集、样本和片段"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.datasets = {}
        self.segments = {}
        self._load_datasets()
    
    def _load_datasets(self):
        """加载所有数据集"""
        # print(f"🔍 开始加载数据集，数据目录: {self.data_dir}")
        
        if not os.path.exists(self.data_dir):
            # print(f"📁 数据目录不存在，创建目录: {self.data_dir}")
            os.makedirs(self.data_dir)
            self._create_sample_data()
            return
        
        # print(f"📁 数据目录存在，开始扫描文件...")
        
        # 加载数据集文件
        for filename in os.listdir(self.data_dir):
            # print(f"📄 发现文件: {filename}")
            if filename.endswith('.json') and not filename.endswith('_segments.json'):
                # 检查文件内容，判断是否为数据集文件
                filepath = os.path.join(self.data_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = json.load(f)
                        # 检查是否包含数据集必需字段
                        if isinstance(content, dict) and 'id' in content and 'samples' in content:
                            dataset_id = filename.replace('.json', '')
                            self.datasets[dataset_id] = content
                            # print(f"✅ 加载数据集文件: {filename} -> {dataset_id}")
                        elif isinstance(content, list) and len(content) > 0:
                            # 处理EgoExo4D格式的数据
                            dataset_id = filename.replace('.json', '')
                            # 转换为标准格式
                            converted_data = self._convert_egoexo4d_format(content, dataset_id)
                            self.datasets[dataset_id] = converted_data
                            # print(f"✅ 转换并加载EgoExo4D数据集: {filename} -> {dataset_id}")
                        else:
                            # 跳过非数据集文件（静默处理）
                            pass
                except Exception as e:
                    print(f"❌ 加载数据集失败 {filename}: {e}")
        
        # 加载片段文件
        for filename in os.listdir(self.data_dir):
            if filename.endswith('.json') and 'segments' in filename:
                dataset_id = filename.replace('_segments.json', '')
                filepath = os.path.join(self.data_dir, filename)
                # print(f"✅ 加载片段文件: {filename} -> {dataset_id}")
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self.segments[dataset_id] = json.load(f)
                        # print(f"✅ 成功加载片段: {dataset_id}")
                except Exception as e:
                    print(f"❌ 加载片段失败 {dataset_id}: {e}")
        
        # 数据集加载完成（静默处理）
        # print(f"📊 数据集加载完成: {len(self.datasets)} 个数据集, {len(self.segments)} 个片段文件")
        
        # 为所有数据集确保有segment文件
        for dataset_id in self.datasets.keys():
            if dataset_id not in self.segments:
                self.segments[dataset_id] = {'segments': []}
                # 创建空的segment文件
                filepath = os.path.join(self.data_dir, f"{dataset_id}_segments.json")
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump({'segments': []}, f, ensure_ascii=False, indent=2)
                    # print(f"📝 为数据集 {dataset_id} 创建空的segment文件")
                except Exception as e:
                    print(f"⚠️ 创建segment文件失败 {dataset_id}: {e}")
        
        # print(f"📋 数据集ID列表: {list(self.datasets.keys())}")
    
    def _convert_egoexo4d_format(self, egoexo4d_data: List[Dict], dataset_id: str) -> Dict:
        """将EgoExo4D格式转换为标准数据集格式"""
        # print(f"🔄 开始转换EgoExo4D格式数据...")
        
        # 创建标准数据集结构
        standard_dataset = {
            "id": dataset_id,
            "name": f"EgoExo4D Dataset ({dataset_id})",
            "description": "Converted from EgoExo4D format",
            "created_at": datetime.now().isoformat(),
            "samples": []
        }
        
        # 转换每个样本
        for i, take in enumerate(egoexo4d_data):
            if 'take_name' in take and 'frame_aligned_videos' in take:
                # 生成样本ID
                sample_id = self._generate_egoexo4d_sample_id(take['take_name'])
                
                # 构建视频路径
                video_paths = []
                if 'frame_aligned_videos' in take and isinstance(take['frame_aligned_videos'], dict):
                    for camera_name, video_path in take['frame_aligned_videos'].items():
                        # 转换为本地静态路径格式
                        local_path = f"/static/videos/{dataset_id}/{sample_id}/{os.path.basename(video_path)}"
                        video_paths.append(local_path)
                
                # 创建标准样本
                sample = {
                    "id": sample_id,
                    "name": take['take_name'],
                    "type": "multiple_videos" if len(video_paths) > 1 else "single_video",
                    "video_paths": video_paths,
                    "video_path": video_paths[0] if video_paths else None,
                    "assigned_to": f"annotator_{(i % 4) + 1}",  # 循环分配标注者
                    "review_status": "未审阅",
                    "created_at": datetime.now().isoformat(),
                    "egoexo4d_metadata": {
                        "take_uid": take.get('take_uid', ''),
                        "root_dir": take.get('root_dir', ''),
                        "best_exo": take.get('best_exo', '')
                    }
                }
                
                standard_dataset["samples"].append(sample)
                # print(f"📹 转换样本: {take['take_name']} -> {sample_id} ({len(video_paths)} 个视频)")
        
        # print(f"✅ EgoExo4D转换完成，共 {len(standard_dataset['samples'])} 个样本")
        return standard_dataset
    
    def _generate_egoexo4d_sample_id(self, take_name: str) -> str:
        """为EgoExo4D样本生成干净的ID"""
        # 移除特殊字符，保留字母、数字和下划线
        clean_id = ''.join(c for c in take_name if c.isalnum() or c == '_')
        # 确保ID不为空
        if not clean_id:
            clean_id = f"sample_{hash(take_name) % 10000}"
        return clean_id
    
    def _create_sample_data(self):
        """创建示例数据用于测试"""
        # 创建示例数据集
        sample_dataset = {
            "id": "test_dataset",
            "name": "Test Dataset",
            "description": "A simple test dataset for video download functionality",
            "created_at": datetime.now().isoformat(),
            "samples": [
                {
                    "id": "test_single",
                    "name": "Test Single Video",
                    "type": "single_video",
                    "video_path": "/static/videos/test_dataset/test_single/video.mp4",
                    "assigned_to": "annotator_1",
                    "review_status": "未审阅",
                    "created_at": datetime.now().isoformat()
                },
                {
                    "id": "test_multi",
                    "name": "Test Multi Video",
                    "type": "multiple_videos",
                    "video_paths": [
                        "/static/videos/test_dataset/test_multi/video1.mp4",
                        "/static/videos/test_dataset/test_multi/video2.mp4"
                    ],
                    "assigned_to": "annotator_1",
                    "review_status": "未审阅",
                    "created_at": datetime.now().isoformat()
                },
                {
                    "id": "test_youtube",
                    "name": "Test YouTube Video",
                    "type": "youtube",
                    "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                    "assigned_to": "annotator_1",
                    "review_status": "未审阅",
                    "created_at": datetime.now().isoformat()
                }
            ]
        }
        
        # 创建示例片段数据
        sample_segments = {
            "segments": [
                {
                    "id": "test_segment_1",
                    "sample_id": "test_single",
                    "video_path": "/static/videos/test_dataset/test_single/video.mp4",
                    "start_time": 0.0,
                    "end_time": 10.0,
                    "status": "待抉择",
                    "created_at": datetime.now().isoformat()
                },
                {
                    "id": "test_segment_2",
                    "sample_id": "test_multi",
                    "video_paths": [
                        "/static/videos/test_dataset/test_multi/video1.mp4",
                        "/static/videos/test_dataset/test_multi/video2.mp4"
                    ],
                    "start_time": 0.0,
                    "end_time": 15.0,
                    "status": "待抉择",
                    "created_at": datetime.now().isoformat()
                }
            ]
        }
        
        # 保存示例数据
        with open(os.path.join(self.data_dir, "test_dataset.json"), 'w', encoding='utf-8') as f:
            json.dump(sample_dataset, f, ensure_ascii=False, indent=2)
        
        with open(os.path.join(self.data_dir, "test_dataset_segments.json"), 'w', encoding='utf-8') as f:
            json.dump(sample_segments, f, ensure_ascii=False, indent=2)
        
        # 重新加载数据
        self._load_datasets()
    
    def get_datasets_for_annotator(self, annotator: str) -> List[Dict]:
        """获取指定标注者的数据集"""
        if not annotator:
            return []
        
        result = []
        for dataset_id, dataset in self.datasets.items():
            # 检查是否有分配给该标注者的样本
            has_assigned_samples = any(
                sample.get('assigned_to') == annotator 
                for sample in dataset.get('samples', [])
            )
            
            if has_assigned_samples:
                result.append({
                    'id': dataset_id,
                    'name': dataset.get('name', 'Unknown'),
                    'description': dataset.get('description', ''),
                    'sample_count': len(dataset.get('samples', [])),
                    'assigned_sample_count': len([
                        s for s in dataset.get('samples', [])
                        if s.get('assigned_to') == annotator
                    ])
                })
        
        return result
    
    def get_samples_for_dataset(self, dataset_id: str, annotator: str) -> List[Dict]:
        """获取指定数据集的样本列表，按审阅状态排序"""
        if dataset_id not in self.datasets:
            return []
        
        dataset = self.datasets[dataset_id]
        samples = dataset.get('samples', [])
        
        # 过滤指定标注者的样本
        if annotator:
            samples = [s for s in samples if s.get('assigned_to') == annotator]
        
        # 按审阅状态排序：审阅中 -> 未审阅 -> 已审阅
        status_order = {'审阅中': 0, '未审阅': 1, '已审阅': 2}
        samples.sort(key=lambda x: status_order.get(x.get('review_status', '未审阅'), 1))
        
        return samples
    
    def get_segments_for_dataset(self, dataset_id: str) -> List[Dict]:
        """获取指定数据集的片段列表（不自动排序）"""
        if dataset_id not in self.segments:
            return []
        
        segments = self.segments[dataset_id].get('segments', [])
        return segments.copy()  # 返回副本，不修改原数据
    
    def get_segments_for_dataset_sorted(self, dataset_id: str) -> List[Dict]:
        """获取指定数据集的片段列表（按状态排序）"""
        if dataset_id not in self.segments:
            return []
        
        segments = self.segments[dataset_id].get('segments', [])
        
        # 按状态排序：待抉择 -> 选用 -> 弃用
        status_order = {'待抉择': 0, '选用': 1, '弃用': 2}
        sorted_segments = segments.copy()
        sorted_segments.sort(key=lambda x: status_order.get(x.get('status', '待抉择'), 0))
        
        return sorted_segments
    
    def get_segments_for_sample(self, sample_id: str) -> List[Dict]:
        """获取指定样本的片段列表"""
        result = []
        for dataset_segments in self.segments.values():
            sample_segments = [
                s for s in dataset_segments.get('segments', [])
                if s.get('sample_id') == sample_id
            ]
            result.extend(sample_segments)
        
        # 按状态排序
        status_order = {'待抉择': 0, '选用': 1, '弃用': 2}
        result.sort(key=lambda x: status_order.get(x.get('status', '待抉择'), 0))
        
        return result
    
    def create_segment(self, segment_data: Dict) -> bool:
        """创建新片段"""
        try:
            sample_id = segment_data.get('sample_id')
            if not sample_id:
                return False
            
            # 找到对应的数据集
            dataset_id = None
            for ds_id, dataset in self.datasets.items():
                if any(s.get('id') == sample_id for s in dataset.get('samples', [])):
                    dataset_id = ds_id
                    break
            
            if not dataset_id:
                return False
            
            # 添加创建时间
            segment_data['created_at'] = datetime.now().isoformat()
            
            # 确保数据集有片段数据结构
            if dataset_id not in self.segments:
                self.segments[dataset_id] = {'segments': []}
            
            # 添加新片段
            self.segments[dataset_id]['segments'].append(segment_data)
            
            # 保存到文件
            filepath = os.path.join(self.data_dir, f"{dataset_id}_segments.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.segments[dataset_id], f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Error creating segment: {e}")
            return False
    
    def update_segment(self, segment_id: str, update_data: Dict) -> bool:
        """更新片段信息（状态、时间、注释等）"""
        try:
            for dataset_id, dataset_segments in self.segments.items():
                for segment in dataset_segments.get('segments', []):
                    if segment.get('id') == segment_id:
                        # 更新状态
                        if 'status' in update_data:
                            segment['status'] = update_data['status']
                        # 更新时间
                        if 'start_time' in update_data:
                            segment['start_time'] = update_data['start_time']
                        if 'end_time' in update_data:
                            segment['end_time'] = update_data['end_time']
                        # 更新注释
                        if 'comment' in update_data:
                            segment['comment'] = update_data['comment']
                        
                        # 保存到文件
                        filepath = os.path.join(self.data_dir, f"{dataset_id}_segments.json")
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(dataset_segments, f, ensure_ascii=False, indent=2)
                        return True
            return False
        except Exception as e:
            print(f"Error updating segment: {e}")
            return False
    
    def update_segment_status(self, segment_id: str, status: str) -> bool:
        """更新片段状态（保持向后兼容）"""
        return self.update_segment(segment_id, {'status': status})
    
    def remove_rejected_segments(self, dataset_id: str) -> bool:
        """删除所有弃用的片段"""
        try:
            if dataset_id not in self.segments:
                return False
            
            dataset_segments = self.segments[dataset_id]
            # 过滤掉弃用的片段
            dataset_segments['segments'] = [
                s for s in dataset_segments.get('segments', [])
                if s.get('status') != '弃用'
            ]
            
            # 保存到文件
            filepath = os.path.join(self.data_dir, f"{dataset_id}_segments.json")
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(dataset_segments, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            print(f"Error removing rejected segments: {e}")
            return False
    
    def delete_segment(self, segment_id: str) -> bool:
        """删除指定片段"""
        try:
            for dataset_id, dataset_segments in self.segments.items():
                for i, segment in enumerate(dataset_segments.get('segments', [])):
                    if segment.get('id') == segment_id:
                        # 删除片段
                        dataset_segments['segments'].pop(i)
                        
                        # 保存到文件
                        filepath = os.path.join(self.data_dir, f"{dataset_id}_segments.json")
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(dataset_segments, f, ensure_ascii=False, indent=2)
                        return True
            return False
        except Exception as e:
            print(f"Error deleting segment: {e}")
            return False
    
    def mark_sample_reviewed(self, sample_id: str) -> bool:
        """标记样本为已审阅"""
        try:
            for dataset_id, dataset in self.datasets.items():
                for sample in dataset.get('samples', []):
                    if sample.get('id') == sample_id:
                        # 更新审阅状态
                        sample['review_status'] = '已审阅'
                        
                        # 保存到文件
                        filepath = os.path.join(self.data_dir, f"{dataset_id}.json")
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(dataset, f, ensure_ascii=False, indent=2)
                        return True
            return False
        except Exception as e:
            print(f"Error marking sample as reviewed: {e}")
            return False
    
    def mark_sample_unreviewed(self, sample_id: str) -> bool:
        """标记样本为未审阅"""
        try:
            for dataset_id, dataset in self.datasets.items():
                for sample in dataset.get('samples', []):
                    if sample.get('id') == sample_id:
                        # 更新审阅状态
                        sample['review_status'] = '未审阅'
                        
                        # 保存到文件
                        filepath = os.path.join(self.data_dir, f"{dataset_id}.json")
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(dataset, f, ensure_ascii=False, indent=2)
                        return True
            return False
        except Exception as e:
            print(f"Error marking sample as unreviewed: {e}")
            return False
    
    def mark_sample_exception(self, sample_id: str) -> bool:
        """标记样本为异常（已弃用，改为自动管理）"""
        print("Warning: mark_sample_exception is deprecated. Exception status is now managed automatically.")
        return False
    
    def set_sample_exception_status(self, sample_id: str, is_exception: bool, reason: str = "") -> bool:
        """设置样本的异常状态（独立于审阅状态）"""
        try:
            for dataset_id, dataset in self.datasets.items():
                for sample in dataset.get('samples', []):
                    if sample.get('id') == sample_id:
                        # 设置异常状态（独立于审阅状态）
                        if is_exception:
                            sample['exception_status'] = {
                                'is_exception': True,
                                'reason': reason,
                                'timestamp': datetime.now().isoformat()
                            }
                        else:
                            # 清除异常状态
                            if 'exception_status' in sample:
                                del sample['exception_status']
                        
                        # 保存到文件
                        filepath = os.path.join(self.data_dir, f"{dataset_id}.json")
                        with open(filepath, 'w', encoding='utf-8') as f:
                            json.dump(dataset, f, ensure_ascii=False, indent=2)
                        return True
            return False
        except Exception as e:
            print(f"Error setting sample exception status: {e}")
            return False
    
    def get_sample_exception_status(self, sample_id: str) -> Optional[Dict]:
        """获取样本的异常状态"""
        try:
            for dataset_id, dataset in self.datasets.items():
                for sample in dataset.get('samples', []):
                    if sample.get('id') == sample_id:
                        return sample.get('exception_status')
            return None
        except Exception as e:
            print(f"Error getting sample exception status: {e}")
            return None
    
    def get_statistics(self, annotator: str = 'all') -> Dict:
        """获取标注统计信息"""
        try:
            statistics = {
                'datasets': {},
                'segments': {},
                'totalSelected': 0
            }
            
            # 统计数据集级别的信息
            for dataset_id, dataset in self.datasets.items():
                # 忽略test_dataset
                if dataset_id == 'test_dataset':
                    continue
                    
                samples = dataset.get('samples', [])
                
                # 过滤指定标注者的样本
                if annotator and annotator != 'all':
                    samples = [s for s in samples if s.get('assigned_to') == annotator]
                
                # 统计审阅状态
                reviewed = len([s for s in samples if s.get('review_status') == '已审阅'])
                unreviewed = len([s for s in samples if s.get('review_status') == '未审阅'])
                
                # 统计异常状态
                exception = len([s for s in samples if s.get('exception_status', {}).get('is_exception', False)])
                
                statistics['datasets'][dataset_id] = {
                    'reviewed': reviewed,
                    'unreviewed': unreviewed,
                    'exception': exception
                }
            
            # 统计片段级别的信息
            all_segments = []
            for dataset_id, dataset_segments in self.segments.items():
                # 忽略test_dataset的片段
                if dataset_id == 'test_dataset':
                    continue
                    
                segments = dataset_segments.get('segments', [])
                
                # 过滤指定标注者的片段（通过sample_id关联）
                if annotator and annotator != 'all':
                    filtered_segments = []
                    for segment in segments:
                        sample_id = segment.get('sample_id')
                        # 查找对应的样本
                        for dataset in self.datasets.values():
                            # 忽略test_dataset
                            if dataset.get('id') == 'test_dataset':
                                continue
                            for sample in dataset.get('samples', []):
                                if sample.get('id') == sample_id and sample.get('assigned_to') == annotator:
                                    filtered_segments.append(segment)
                                    break
                    segments = filtered_segments
                
                all_segments.extend(segments)
            
            # 统计片段状态
            selected = len([s for s in all_segments if s.get('status') == '选用'])
            pending = len([s for s in all_segments if s.get('status') == '待抉择'])
            rejected = len([s for s in all_segments if s.get('status') == '弃用'])
            
            statistics['segments'] = {
                'selected': selected,
                'pending': pending,
                'rejected': rejected
            }
            
            # 按长度和状态统计片段
            length_status_stats = {
                'short': {'selected': 0, 'pending': 0, 'rejected': 0},      # ≤5秒
                'medium': {'selected': 0, 'pending': 0, 'rejected': 0},     # (5-13秒]
                'long': {'selected': 0, 'pending': 0, 'rejected': 0},       # (13-30秒]
                'extraLong': {'selected': 0, 'pending': 0, 'rejected': 0},  # >30秒
                'all': {'selected': 0, 'pending': 0, 'rejected': 0}         # 所有长度
            }
            
            for segment in all_segments:
                start_time = segment.get('start_time', 0)
                end_time = segment.get('end_time', 0)
                duration = end_time - start_time
                status = segment.get('status', '待抉择')
                
                # 更新所有长度的统计
                if status == '选用':
                    length_status_stats['all']['selected'] += 1
                elif status == '待抉择':
                    length_status_stats['all']['pending'] += 1
                elif status == '弃用':
                    length_status_stats['all']['rejected'] += 1
                
                # 按长度分类统计
                if duration <= 5:
                    if status == '选用':
                        length_status_stats['short']['selected'] += 1
                    elif status == '待抉择':
                        length_status_stats['short']['pending'] += 1
                    elif status == '弃用':
                        length_status_stats['short']['rejected'] += 1
                elif duration <= 13:
                    if status == '选用':
                        length_status_stats['medium']['selected'] += 1
                    elif status == '待抉择':
                        length_status_stats['medium']['pending'] += 1
                    elif status == '弃用':
                        length_status_stats['medium']['rejected'] += 1
                elif duration <= 30:
                    if status == '选用':
                        length_status_stats['long']['selected'] += 1
                    elif status == '待抉择':
                        length_status_stats['long']['pending'] += 1
                    elif status == '弃用':
                        length_status_stats['long']['rejected'] += 1
                else:
                    if status == '选用':
                        length_status_stats['extraLong']['selected'] += 1
                    elif status == '待抉择':
                        length_status_stats['extraLong']['pending'] += 1
                    elif status == '弃用':
                        length_status_stats['extraLong']['rejected'] += 1
            
            # 更新统计信息
            statistics['segments'].update({
                'lengthStatus': length_status_stats
            })
            
            # 总选用片段数
            statistics['totalSelected'] = length_status_stats['all']['selected']
            
            return statistics
            
        except Exception as e:
            print(f"Error getting statistics: {e}")
            return {
                'datasets': {},
                'segments': {},
                'totalSelected': 0
            }
