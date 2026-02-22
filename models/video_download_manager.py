import os
import zipfile
import requests
import shutil
from typing import Dict, List, Optional, Tuple
import logging

# 可选依赖
try:
    import yt_dlp
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    print("警告: yt-dlp 不可用，YouTube下载功能将受限")

try:
    from huggingface_hub import hf_hub_download
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False
    print("警告: huggingface_hub 不可用，HuggingFace下载功能将受限")

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VideoDownloadManager:
    """视频下载管理器，处理YouTube和HuggingFace视频下载"""
    
    def __init__(self, base_video_dir: str = None, dataset_manager=None):
        # 如果没有指定，使用项目根目录下的static/videos
        if base_video_dir is None:
            # 获取当前文件所在目录的上级目录（项目根目录）
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(current_dir)
            self.base_video_dir = os.path.join(project_root, "static", "videos")
        else:
            self.base_video_dir = base_video_dir
            
        self.hf_repo = "GuangsTrip/spatialpredictsource"
        self.hf_repo_type = "dataset"  # 明确指定为数据集仓库
        
        # 数据集管理器引用，用于管理异常状态
        self.dataset_manager = dataset_manager
        
        # 确保基础目录存在
        os.makedirs(self.base_video_dir, exist_ok=True)
        logger.info(f"视频下载管理器初始化完成，基础目录: {self.base_video_dir}")
    
    def check_video_exists(self, dataset_name: str, sample_name: str, video_filename: str) -> bool:
        """检查本地视频文件是否存在"""
        video_path = os.path.join(self.base_video_dir, dataset_name, sample_name, video_filename)
        return os.path.exists(video_path)
    
    def get_video_path(self, dataset_name: str, sample_name: str, video_filename: str) -> str:
        """获取视频的完整路径"""
        return os.path.join(self.base_video_dir, dataset_name, sample_name, video_filename)
    
    def get_video_status(self, dataset_name: str, sample_name: str, video_filename: str) -> Dict[str, str]:
        """获取视频状态信息"""
        video_path = self.get_video_path(dataset_name, sample_name, video_filename)
        
        if os.path.exists(video_path):
            # 获取文件大小
            file_size = os.path.getsize(video_path)
            return {
                "status": "已下载",
                "path": video_path,
                "size": self.format_file_size(file_size),
                "exists": True
            }
        else:
            return {
                "status": "未下载",
                "path": video_path,
                "size": "0B",
                "exists": False
            }
    
    def download_youtube_video(self, youtube_url: str, dataset_name: str, sample_name: str, 
                              video_filename: str) -> Dict[str, str]:
        """从YouTube下载视频"""
        if not YT_DLP_AVAILABLE:
            return {
                "success": False,
                "message": "yt-dlp 不可用，无法下载YouTube视频。请安装: pip install yt-dlp"
            }
        
        try:
            # 创建目标目录
            target_dir = os.path.join(self.base_video_dir, dataset_name, sample_name)
            os.makedirs(target_dir, exist_ok=True)
            
            target_path = os.path.join(target_dir, video_filename)
            
            # 使用与FrameQuiz完全相同的命令行调用方式
            logger.info(f"开始下载YouTube视频: {youtube_url}")
            logger.info(f"目标路径: {target_path}")
            
            # 使用最兼容的下载策略，添加额外的兼容性参数
            command = [
                'yt-dlp',
                '-o', target_path,
                '--merge-output-format', 'mp4',
                '--no-warnings',  # 减少警告输出
                '--retries', '3',  # 重试3次
                '--fragment-retries', '3',  # 片段重试3次
                '--extractor-retries', '3',  # 提取器重试3次
                youtube_url
            ]
            
            logger.info(f"执行命令: {' '.join(command)}")
            
            # 使用subprocess调用，与FrameQuiz完全一致
            try:
                import subprocess
                # 确保使用正确的环境变量，特别是conda环境
                env = os.environ.copy()
                # 确保PATH包含conda的bin目录
                conda_bin = "/opt/homebrew/Caskroom/miniconda/base/bin"
                if conda_bin not in env.get('PATH', ''):
                    env['PATH'] = conda_bin + ':' + env.get('PATH', '')
                
                logger.info(f"使用环境PATH: {env['PATH']}")
                
                # 使用与FrameQuiz完全相同的subprocess调用方式
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
                stdout, stderr = process.communicate()
                
                if process.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown error"
                    logger.warning(f"FrameQuiz策略失败，尝试兼容策略: {error_msg}")
                    
                    # 如果FrameQuiz策略失败，尝试更兼容的格式选择
                    fallback_command = [
                        'yt-dlp',
                        '-f', 'best[ext=mp4]/best',  # 更兼容的格式选择
                        '-o', target_path,
                        '--merge-output-format', 'mp4',
                        youtube_url
                    ]
                    
                    logger.info("尝试兼容策略下载...")
                    fallback_process = subprocess.Popen(fallback_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
                    fallback_stdout, fallback_stderr = fallback_process.communicate()
                    
                    if fallback_process.returncode != 0:
                        fallback_error = fallback_stderr.decode() if fallback_stderr else "Unknown error"
                        logger.error(f"兼容策略也失败: {fallback_error}")
                        raise Exception(f"All download strategies failed. FrameQuiz: {error_msg}, Fallback: {fallback_error}")
                    
                    logger.info("兼容策略下载成功")
                else:
                    logger.info("FrameQuiz策略下载成功")
                
                logger.info("YouTube视频下载完成")
                
            except Exception as e:
                logger.error(f"YouTube视频下载失败: {str(e)}")
                raise e
            
            # 检查下载是否成功
            if os.path.exists(target_path):
                file_size = os.path.getsize(target_path)
                
                # 验证文件完整性
                if file_size > 0:
                    # 尝试获取视频时长等信息来验证文件
                    validation_result = self._validate_video_file(target_path)
                    
                    if validation_result["valid"]:
                        logger.info(f"YouTube视频下载成功: {target_path}, 大小: {self.format_file_size(file_size)}")
                        
                        # 下载成功时清除异常状态
                        if self.dataset_manager:
                            try:
                                sample_id = sample_name
                                self.dataset_manager.set_sample_exception_status(sample_id, False)
                                logger.info(f"已清除样本 {sample_id} 的异常状态")
                            except Exception as status_error:
                                logger.error(f"清除异常状态失败: {status_error}")
                        
                        return {
                            "success": True,
                            "message": "YouTube视频下载成功",
                            "path": target_path,
                            "size": self.format_file_size(file_size),
                            "duration": validation_result.get("duration", "Unknown"),
                            "format": validation_result.get("format", "Unknown")
                        }
                    else:
                        # 文件存在但验证失败，尝试删除并重新下载
                        logger.warning(f"视频文件验证失败: {validation_result['message']}")
                        os.remove(target_path)
                        return {
                            "success": False,
                            "message": f"视频文件验证失败: {validation_result['message']}"
                        }
                else:
                    # 文件大小为0，删除并返回错误
                    os.remove(target_path)
                    return {
                        "success": False,
                        "message": "YouTube视频下载失败：文件大小为0"
                    }
            else:
                return {
                    "success": False,
                    "message": "YouTube视频下载失败：文件未创建"
                }
                
        except Exception as e:
            logger.error(f"YouTube视频下载失败: {str(e)}")
            # 清理可能的部分下载文件
            if os.path.exists(target_path):
                try:
                    os.remove(target_path)
                    logger.info(f"已清理部分下载文件: {target_path}")
                except:
                    pass
            
            # 自动设置异常状态
            if self.dataset_manager:
                try:
                    # 从sample_name中提取sample_id（假设sample_name就是sample_id）
                    sample_id = sample_name
                    self.dataset_manager.set_sample_exception_status(
                        sample_id, 
                        True, 
                        "下载异常，请稍后再试"
                    )
                    logger.info(f"已自动设置样本 {sample_id} 为异常状态")
                except Exception as status_error:
                    logger.error(f"设置异常状态失败: {status_error}")
            
            return {
                "success": False,
                "message": f"YouTube视频下载失败: {str(e)}"
            }
    
    def _validate_video_file(self, video_path: str) -> Dict[str, str]:
        """验证视频文件的有效性"""
        try:
            import subprocess
            import json
            
            # 使用ffprobe检查视频文件
            cmd = [
                'ffprobe', 
                '-v', 'quiet', 
                '-print_format', 'json', 
                '-show_format', 
                '-show_streams', 
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                try:
                    info = json.loads(result.stdout)
                    
                    # 检查是否有视频流
                    if 'streams' in info and any(s.get('codec_type') == 'video' for s in info['streams']):
                        format_info = info.get('format', {})
                        duration = format_info.get('duration', 'Unknown')
                        format_name = format_info.get('format_name', 'Unknown')
                        
                        return {
                            "valid": True,
                            "duration": duration,
                            "format": format_name,
                            "message": "视频文件验证成功"
                        }
                    else:
                        return {
                            "valid": False,
                            "message": "文件不包含有效的视频流"
                        }
                        
                except json.JSONDecodeError:
                    return {
                        "valid": False,
                        "message": "无法解析视频文件信息"
                    }
            else:
                return {
                    "valid": False,
                    "message": f"ffprobe检查失败: {result.stderr}"
                }
                
        except subprocess.TimeoutExpired:
            return {
                "valid": False,
                "message": "视频文件检查超时"
            }
        except FileNotFoundError:
            # ffprobe不存在，使用基本的文件检查
            return self._basic_video_validation(video_path)
        except Exception as e:
            return {
                "valid": False,
                "message": f"视频文件验证异常: {str(e)}"
            }
    
    def _basic_video_validation(self, video_path: str) -> Dict[str, str]:
        """基本的视频文件验证（当ffprobe不可用时）"""
        try:
            # 检查文件扩展名
            if not self._is_video_file(os.path.basename(video_path)):
                return {
                    "valid": False,
                    "message": "文件扩展名不是有效的视频格式"
                }
            
            # 检查文件大小（至少1KB）
            file_size = os.path.getsize(video_path)
            if file_size < 1024:
                return {
                    "valid": False,
                    "message": "文件大小过小，可能损坏"
                }
            
            # 检查文件头部（简单的魔数检查）
            with open(video_path, 'rb') as f:
                header = f.read(16)
                
                # MP4文件魔数检查
                if header.startswith(b'\x00\x00\x00\x18ftypmp4') or \
                   header.startswith(b'\x00\x00\x00\x20ftypmp4') or \
                   header.startswith(b'\x00\x00\x00\x1cftypisom'):
                    return {
                        "valid": True,
                        "duration": "Unknown",
                        "format": "MP4",
                        "message": "MP4文件基本验证通过"
                    }
                
                # 其他格式的简单检查
                return {
                    "valid": True,
                    "duration": "Unknown",
                    "format": "Unknown",
                    "message": "文件基本验证通过"
                }
                
        except Exception as e:
            return {
                "valid": False,
                "message": f"基本验证失败: {str(e)}"
            }
    
    def download_huggingface_video(self, dataset_name: str, sample_name: str) -> Dict[str, str]:
        """从HuggingFace下载视频压缩包并解压"""
        if not HF_HUB_AVAILABLE:
            return {
                "success": False,
                "message": "huggingface_hub 不可用，无法下载HuggingFace视频。请安装: pip install huggingface_hub"
            }
        
        try:
            # 创建目标目录
            target_dir = os.path.join(self.base_video_dir, dataset_name, sample_name)
            os.makedirs(target_dir, exist_ok=True)
            
            # 压缩包文件名
            zip_filename = f"{sample_name}.zip"
            zip_path = os.path.join(target_dir, zip_filename)
            
            # 从HuggingFace下载压缩包
            logger.info(f"开始从HuggingFace下载: {self.hf_repo}/videos/{dataset_name}/{zip_filename}")
            
            try:
                downloaded_path = hf_hub_download(
                    repo_id=self.hf_repo,
                    repo_type="dataset",  # 明确指定为数据集仓库
                    filename=f"videos/{dataset_name}/{zip_filename}",
                    local_dir=target_dir,
                    local_dir_use_symlinks=False
                )
                
                # 如果下载成功，解压文件
                if os.path.exists(downloaded_path):
                    logger.info(f"压缩包下载成功: {downloaded_path}")
                    
                    # 解压文件
                    extract_result = self._extract_zip_file(downloaded_path, target_dir)
                    
                    if extract_result["success"]:
                        # 删除压缩包
                        os.remove(downloaded_path)
                        logger.info(f"压缩包已删除: {downloaded_path}")
                        
                        # 清理多余的目录结构
                        self._cleanup_extraction_dirs(target_dir)
                        
                        return {
                            "success": True,
                            "message": "视频下载并解压成功",
                            "extracted_files": extract_result["files"],
                            "path": target_dir
                        }
                    else:
                        return extract_result
                else:
                    return {
                        "success": False,
                        "message": "压缩包下载失败：文件未创建"
                    }
                    
            except Exception as e:
                logger.error(f"HuggingFace下载失败: {str(e)}")
                return {
                    "success": False,
                    "message": f"HuggingFace下载失败: {str(e)}"
                }
                
        except Exception as e:
            logger.error(f"视频下载过程失败: {str(e)}")
            return {
                "success": False,
                "message": f"视频下载过程失败: {str(e)}"
            }
    
    def _extract_zip_file(self, zip_path: str, extract_dir: str) -> Dict[str, str]:
        """解压ZIP文件"""
        try:
            extracted_files = []
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 获取压缩包中的文件列表
                file_list = zip_ref.namelist()
                
                # 解压所有文件，只保留文件名，不保持目录结构
                for file_name in file_list:
                    # 跳过目录
                    if file_name.endswith('/'):
                        continue
                    
                    # 只获取文件名，不包含路径
                    base_filename = os.path.basename(file_name)
                    
                    # 解压到目标目录，使用基础文件名
                    zip_ref.extract(file_name, extract_dir)
                    
                    # 如果解压后的文件不在目标目录根目录，需要移动
                    extracted_file_path = os.path.join(extract_dir, file_name)
                    target_file_path = os.path.join(extract_dir, base_filename)
                    
                    # 如果文件不在根目录，移动到根目录
                    if extracted_file_path != target_file_path:
                        if os.path.exists(target_file_path):
                            os.remove(target_file_path)  # 如果目标文件已存在，先删除
                        shutil.move(extracted_file_path, target_file_path)
                        extracted_file_path = target_file_path
                    
                    # 如果是视频文件，添加到列表
                    if self._is_video_file(base_filename):
                        extracted_files.append({
                            "filename": base_filename,
                            "path": extracted_file_path,
                            "size": self.format_file_size(os.path.getsize(extracted_file_path))
                        })
                
                logger.info(f"解压完成，共解压 {len(extracted_files)} 个视频文件")
                
                return {
                    "success": True,
                    "message": f"解压成功，共 {len(extracted_files)} 个视频文件",
                    "files": extracted_files
                }
                
        except Exception as e:
            logger.error(f"解压失败: {str(e)}")
            return {
                "success": False,
                "message": f"解压失败: {str(e)}"
            }
    
    def _cleanup_extraction_dirs(self, target_dir: str):
        """清理解压后产生的多余目录结构"""
        try:
            # 查找并删除多余的目录
            for item in os.listdir(target_dir):
                item_path = os.path.join(target_dir, item)
                
                # 删除 __MACOSX 目录（macOS解压产生的垃圾目录）
                if item == '__MACOSX':
                    shutil.rmtree(item_path)
                    logger.info(f"已删除垃圾目录: {item_path}")
                    continue
                
                # 删除 videos 目录（ZIP内部路径结构）
                if item == 'videos' and os.path.isdir(item_path):
                    # 检查videos目录下是否有内容
                    videos_content = os.listdir(item_path)
                    if len(videos_content) == 1 and os.path.isdir(os.path.join(item_path, videos_content[0])):
                        # 如果videos下只有一个目录，且该目录为空或只包含视频文件，则删除整个videos目录
                        inner_dir = os.path.join(item_path, videos_content[0])
                        inner_content = os.listdir(inner_dir)
                        if all(self._is_video_file(f) for f in inner_content):
                            # 移动视频文件到目标目录
                            for video_file in inner_content:
                                src_path = os.path.join(inner_dir, video_file)
                                dst_path = os.path.join(target_dir, video_file)
                                if not os.path.exists(dst_path):
                                    shutil.move(src_path, dst_path)
                                    logger.info(f"已移动视频文件: {video_file}")
                            
                            # 删除整个videos目录结构
                            shutil.rmtree(item_path)
                            logger.info(f"已清理多余目录结构: {item_path}")
                    
        except Exception as e:
            logger.warning(f"清理多余目录时出错: {str(e)}")
    
    def _is_video_file(self, filename: str) -> bool:
        """判断是否为视频文件"""
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
        return any(filename.lower().endswith(ext) for ext in video_extensions)
    
    def _youtube_progress_hook(self, d):
        """YouTube下载进度回调"""
        if d['status'] == 'downloading':
            if 'total_bytes' in d and d['total_bytes']:
                percent = (d['downloaded_bytes'] / d['total_bytes']) * 100
                logger.info(f"YouTube下载进度: {percent:.1f}%")
            elif 'downloaded_bytes' in d:
                logger.info(f"YouTube已下载: {self.format_file_size(d['downloaded_bytes'])}")
        elif d['status'] == 'finished':
            logger.info("YouTube下载完成，正在处理...")
    
    def format_file_size(self, size_bytes: int) -> str:
        """格式化文件大小"""
        if size_bytes == 0:
            return "0B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f}{size_names[i]}"
    
    def get_sample_video_status(self, dataset_name: str, sample_name: str, 
                               video_paths: List[str]) -> List[Dict[str, str]]:
        """获取样本中所有视频的状态"""
        video_statuses = []
        
        for video_path in video_paths:
            # 从完整路径中提取文件名
            video_filename = os.path.basename(video_path)
            status = self.get_video_status(dataset_name, sample_name, video_filename)
            video_statuses.append({
                "original_path": video_path,
                "filename": video_filename,
                **status
            })
        
        return video_statuses
    
    def cleanup_temp_files(self, dataset_name: str, sample_name: str):
        """清理临时文件"""
        try:
            temp_dir = os.path.join(self.base_video_dir, dataset_name, sample_name)
            
            # 查找并删除临时文件
            for filename in os.listdir(temp_dir):
                if filename.endswith('.tmp') or filename.endswith('.part'):
                    temp_path = os.path.join(temp_dir, filename)
                    os.remove(temp_path)
                    logger.info(f"已删除临时文件: {temp_path}")
                    
        except Exception as e:
            logger.error(f"清理临时文件失败: {str(e)}")
    
    def delete_video_files(self, dataset_name: str, sample_name: str, video_type: str) -> Dict[str, str]:
        """删除样本的本地视频文件"""
        try:
            local_dir = os.path.join(self.base_video_dir, dataset_name, sample_name)
            
            if not os.path.exists(local_dir):
                return {
                    'success': False,
                    'message': f'本地目录不存在: {local_dir}'
                }
            
            deleted_files = []
            deleted_size = 0
            
            # 根据视频类型删除相应的文件
            if video_type == 'youtube':
                # 删除YouTube视频文件
                youtube_file = os.path.join(local_dir, f"{sample_name}_youtube.mp4")
                if os.path.exists(youtube_file):
                    file_size = os.path.getsize(youtube_file)
                    os.remove(youtube_file)
                    deleted_files.append(f"{sample_name}_youtube.mp4")
                    deleted_size += file_size
                    logger.info(f"已删除YouTube视频文件: {youtube_file}")
                
            elif video_type in ['single_video', 'multiple_videos']:
                # 删除所有视频文件
                for filename in os.listdir(local_dir):
                    if self._is_video_file(filename):
                        file_path = os.path.join(local_dir, filename)
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_files.append(filename)
                        deleted_size += file_size
                        logger.info(f"已删除视频文件: {file_path}")
            
            # 如果目录为空，删除目录
            if not os.listdir(local_dir):
                os.rmdir(local_dir)
                logger.info(f"已删除空目录: {local_dir}")
            
            if deleted_files:
                return {
                    'success': True,
                    'message': f'成功删除 {len(deleted_files)} 个视频文件，释放空间 {self.format_file_size(deleted_size)}',
                    'deleted_files': deleted_files,
                    'deleted_size': self.format_file_size(deleted_size)
                }
            else:
                return {
                    'success': True,
                    'message': '没有找到需要删除的视频文件'
                }
                
        except Exception as e:
            logger.error(f"删除视频文件失败: {str(e)}")
            return {
                'success': False,
                'message': f'删除失败: {str(e)}'
            }
