from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS
import json
import os
import logging
from datetime import datetime
from models.dataset_manager import DatasetManager
from models.annotation_manager import AnnotationManager
from models.video_download_manager import VideoDownloadManager
from models.qa_manager import QAManager
from models.candidate_qa_manager import candidate_qa_manager, CandidateQAManager
from models.video_path_manager import video_path_manager
from config import config

# 创建Flask应用
app = Flask(__name__)

# 加载配置
config_name = os.environ.get('FLASK_CONFIG', 'default')
app.config.from_object(config[config_name])
config[config_name].init_app(app)

# 启用CORS
CORS(app)

# 配置日志
logging.basicConfig(
    level=getattr(logging, app.config['LOG_LEVEL']),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(app.config['LOG_FILE']),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 初始化管理器
dataset_manager = DatasetManager()
annotation_manager = AnnotationManager()
video_download_manager = VideoDownloadManager(dataset_manager=dataset_manager)
qa_manager = QAManager()
# 使用候选QA管理器作为主要QA管理器

@app.route('/')
def index():
    """默认进入QA检查页面"""
    return redirect(url_for('qa_review'))

@app.route('/video-test')
def video_test():
    """视频播放测试页面"""
    return render_template('video_test.html')

@app.route('/simple-video-test')
def simple_video_test():
    """简单视频测试页面"""
    return render_template('simple_video_test.html')

@app.route('/youtube-test')
def youtube_test():
    """YouTube视频播放测试页面"""
    return render_template('test_youtube_player.html')

@app.route('/path-debug')
def path_debug():
    """路径调试测试页面"""
    return render_template('test_path_debug.html')

@app.route('/api/annotators')
def get_annotators():
    """获取所有标注者列表"""
    return jsonify(annotation_manager.get_all_annotators())

@app.route('/api/datasets')
def get_datasets():
    """获取所有数据集列表"""
    annotator = request.args.get('annotator')
    return jsonify(dataset_manager.get_datasets_for_annotator(annotator))

@app.route('/api/dataset/<dataset_id>/samples')
def get_dataset_samples(dataset_id):
    """获取指定数据集的样本列表"""
    annotator = request.args.get('annotator')
    return jsonify(dataset_manager.get_samples_for_dataset(dataset_id, annotator))

@app.route('/api/dataset/<dataset_id>/segments')
def get_dataset_segments(dataset_id):
    """获取指定数据集的片段列表"""
    return jsonify(dataset_manager.get_segments_for_dataset(dataset_id))

@app.route('/api/sample/<sample_id>/segments')
def get_sample_segments(sample_id):
    """获取指定样本的片段列表"""
    return jsonify(dataset_manager.get_segments_for_sample(sample_id))

@app.route('/api/segment/<segment_id>/update', methods=['POST'])
def update_segment(segment_id):
    """更新片段状态和时间"""
    data = request.json
    success = dataset_manager.update_segment(segment_id, data)
    return jsonify({'success': success})

@app.route('/api/segment/<segment_id>/comment', methods=['POST'])
def update_segment_comment(segment_id):
    """更新片段注释"""
    data = request.json
    comment = data.get('comment', '')
    success = dataset_manager.update_segment(segment_id, {'comment': comment})
    return jsonify({'success': success})

@app.route('/api/segment/create', methods=['POST'])
def create_segment():
    """创建新片段"""
    data = request.json
    segment_data = {
        'id': data.get('id'),
        'video_path': data.get('video_path'),
        'start_time': data.get('start_time'),
        'end_time': data.get('end_time'),
        'status': data.get('status', '待抉择'),
        'sample_id': data.get('sample_id')
    }
    success = dataset_manager.create_segment(segment_data)
    return jsonify({'success': success, 'segment': segment_data if success else None})

@app.route('/api/dataset/<dataset_id>/remove_rejected', methods=['POST'])
def remove_rejected_segments(dataset_id):
    """删除所有弃用的片段"""
    success = dataset_manager.remove_rejected_segments(dataset_id)
    return jsonify({'success': success})

@app.route('/api/annotator/select', methods=['POST'])
def select_annotator():
    """选择标注者身份"""
    data = request.json
    annotator = data.get('annotator')
    annotation_manager.set_current_annotator(annotator)
    return jsonify({'success': True, 'annotator': annotator})

@app.route('/api/video/status', methods=['GET'])
def get_video_status():
    """获取视频状态信息"""
    dataset_name = request.args.get('dataset')
    sample_name = request.args.get('sample')
    video_paths = request.args.getlist('video_paths[]')
    
    if not dataset_name or not sample_name or not video_paths:
        return jsonify({'error': '缺少必要参数'}), 400
    
    video_statuses = video_download_manager.get_sample_video_status(
        dataset_name, sample_name, video_paths
    )
    
    return jsonify({'video_statuses': video_statuses})

@app.route('/api/video/download', methods=['POST'])
def download_video():
    """下载视频"""
    data = request.json
    dataset_name = data.get('dataset')
    sample_name = data.get('sample')
    video_type = data.get('type')  # 'youtube', 'single_video', 'multiple_videos'
    video_info = data.get('video_info')  # 具体信息
    
    if not dataset_name or not sample_name or not video_type:
        return jsonify({'error': '缺少必要参数'}), 400
    
    try:
        if video_type == 'youtube':
            # YouTube视频下载
            youtube_url = video_info.get('youtube_url')
            video_filename = f"{sample_name}_youtube.mp4"
            
            result = video_download_manager.download_youtube_video(
                youtube_url, dataset_name, sample_name, video_filename
            )
            
        elif video_type in ['single_video', 'multiple_videos']:
            # HuggingFace视频下载
            result = video_download_manager.download_huggingface_video(
                dataset_name, sample_name
            )
            
        else:
            return jsonify({'error': '不支持的视频类型'}), 400
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': f'下载失败: {str(e)}'}), 500

@app.route('/api/video/delete', methods=['POST'])
def delete_video():
    """删除视频文件"""
    data = request.json
    dataset_name = data.get('dataset')
    sample_name = data.get('sample')
    video_type = data.get('type')
    
    if not dataset_name or not sample_name or not video_type:
        return jsonify({'error': '缺少必要参数'}), 400
    
    try:
        result = video_download_manager.delete_video_files(dataset_name, sample_name, video_type)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({'error': f'删除失败: {str(e)}'}), 500

@app.route('/api/segment/<segment_id>/delete', methods=['DELETE'])
def delete_segment(segment_id):
    """删除指定片段"""
    try:
        success = dataset_manager.delete_segment(segment_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'error': f'删除片段失败: {str(e)}'}), 500

@app.route('/api/sample/<sample_id>/mark_reviewed', methods=['POST'])
def mark_sample_reviewed(sample_id):
    """标记样本为已审阅"""
    try:
        success = dataset_manager.mark_sample_reviewed(sample_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'error': f'标记样本失败: {str(e)}'}), 500

@app.route('/api/sample/<sample_id>/mark_unreviewed', methods=['POST'])
def mark_sample_unreviewed(sample_id):
    """标记样本为未审阅"""
    try:
        success = dataset_manager.mark_sample_unreviewed(sample_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'error': f'设置样本失败: {str(e)}'}), 500

@app.route('/api/sample/<sample_id>/exception_status', methods=['GET'])
def get_sample_exception_status(sample_id):
    """获取样本的异常状态"""
    try:
        exception_status = dataset_manager.get_sample_exception_status(sample_id)
        return jsonify({'exception_status': exception_status})
    except Exception as e:
        return jsonify({'error': f'获取异常状态失败: {str(e)}'}), 500

@app.route('/api/statistics', methods=['GET'])
def get_statistics():
    """获取标注统计信息"""
    try:
        # 获取当前标注者（从请求参数或session中获取）
        current_annotator = request.args.get('annotator', 'all')
        
        # 获取统计数据
        statistics = dataset_manager.get_statistics(current_annotator)
        return jsonify(statistics)
        
    except Exception as e:
        return jsonify({'error': f'获取统计数据失败: {str(e)}'}), 500

# QA相关API端点
@app.route('/qa-review')
def qa_review():
    """QA检查页面"""
    return render_template('qa_review.html')

@app.route('/api/qa/segments')
def get_qa_segments():
    """获取所有QA segments"""
    try:
        segments = candidate_qa_manager.get_all_segments()
        return jsonify({'segments': segments})
    except Exception as e:
        return jsonify({'error': f'获取QA segments失败: {str(e)}'}), 500

@app.route('/api/qa/segment/<segment_id>/qas')
def get_segment_qas(segment_id):
    """获取指定segment的所有QA"""
    try:
        qas = candidate_qa_manager.get_segment_qas(segment_id)
        return jsonify({'qas': qas})
    except Exception as e:
        return jsonify({'error': f'获取segment QA失败: {str(e)}'}), 500

@app.route('/api/qa/qa/<qa_id>', methods=['PUT'])
def update_qa(qa_id):
    """更新QA信息（自动保存）"""
    try:
        data = request.json
        success = candidate_qa_manager.update_qa(qa_id, data)
        return jsonify({'success': success, 'message': '已自动保存'})
    except Exception as e:
        return jsonify({'error': f'更新QA失败: {str(e)}'}), 500

@app.route('/api/qa/qa/<qa_id>/auto-save', methods=['POST'])
def auto_save_qa(qa_id):
    """自动保存QA信息（已集成到update_qa中）"""
    try:
        data = request.json
        success = candidate_qa_manager.update_qa(qa_id, data)
        return jsonify({'success': success, 'message': '已自动保存'})
    except Exception as e:
        return jsonify({'error': f'自动保存失败: {str(e)}'}), 500

@app.route('/api/qa/qa/<qa_id>', methods=['DELETE'])
def delete_qa(qa_id):
    """删除QA（自动保存）"""
    try:
        success = candidate_qa_manager.delete_qa(qa_id)
        return jsonify({'success': success, 'message': '已自动保存'})
    except Exception as e:
        return jsonify({'error': f'删除QA失败: {str(e)}'}), 500

@app.route('/api/qa/segment/<segment_id>/qa', methods=['POST'])
def add_qa(segment_id):
    """添加新的QA（自动保存）"""
    try:
        data = request.json
        success = candidate_qa_manager.add_qa(segment_id, data)
        return jsonify({'success': success, 'message': '已自动保存'})
    except Exception as e:
        return jsonify({'error': f'添加QA失败: {str(e)}'}), 500

@app.route('/api/qa/statistics')
def get_qa_statistics():
    """获取QA统计信息"""
    try:
        statistics = candidate_qa_manager.get_qa_statistics()
        return jsonify(statistics)
    except Exception as e:
        return jsonify({'error': f'获取QA统计失败: {str(e)}'}), 500

@app.route('/api/qa/segment/<segment_id>/status', methods=['POST'])
def update_segment_status(segment_id):
    """更新segment状态"""
    try:
        data = request.json
        new_status = data.get('status')
        success = candidate_qa_manager.update_segment_status(segment_id, new_status)
        return jsonify({'success': success, 'message': '状态更新成功'})
    except Exception as e:
        return jsonify({'error': f'更新状态失败: {str(e)}'}), 500

@app.route('/api/qa/segment/<segment_id>/video')
def get_segment_video_path(segment_id):
    """获取segment对应的视频文件路径"""
    try:
        video_info = candidate_qa_manager.get_video_info_for_segment(segment_id)
        if not video_info:
            return jsonify({'error': '找不到视频信息'}), 404
        
        return jsonify({
            'video_path': video_info.get('video_path'),
            'video_name': video_info.get('video_name'),
            'video_type': video_info.get('video_type'),
            'current_perspective': video_info.get('current_perspective'),
            'available_perspectives': video_info.get('available_perspectives', [])
        })
    except Exception as e:
        return jsonify({'error': f'获取视频路径失败: {str(e)}'}), 500

@app.route('/api/video/directory/set', methods=['POST'])
def set_video_directory():
    """设置视频文件目录"""
    try:
        data = request.json
        video_dir = data.get('video_dir')
        
        if not video_dir or not os.path.exists(video_dir):
            return jsonify({'error': '无效的视频目录路径'}), 400
        
        # 设置视频目录
        candidate_qa_manager.set_video_base_directory(video_dir)
        video_path_manager.set_base_video_dir(video_dir)
        
        # 扫描视频文件
        video_map = video_path_manager.scan_video_directory()
        
        return jsonify({
            'success': True,
            'video_dir': video_dir,
            'video_count': len(video_map),
            'videos': list(video_map.keys())
        })
    except Exception as e:
        return jsonify({'error': f'设置视频目录失败: {str(e)}'}), 500

@app.route('/api/video/directory/current')
def get_current_video_directory():
    """获取当前视频目录"""
    try:
        return jsonify({
            'video_dir': video_path_manager.base_video_dir,
            'exists': os.path.exists(video_path_manager.base_video_dir)
        })
    except Exception as e:
        return jsonify({'error': f'获取视频目录失败: {str(e)}'}), 500

@app.route('/api/video/list')
def list_all_videos():
    """列出所有可用的视频"""
    try:
        videos = video_path_manager.list_all_videos()
        return jsonify({'videos': videos})
    except Exception as e:
        return jsonify({'error': f'获取视频列表失败: {str(e)}'}), 500

@app.route('/api/video/<video_name>/perspectives')
def get_video_perspectives(video_name):
    """获取指定视频的所有视角"""
    try:
        perspectives = video_path_manager.get_available_perspectives(video_name)
        return jsonify({'perspectives': perspectives})
    except Exception as e:
        return jsonify({'error': f'获取视频视角失败: {str(e)}'}), 500

@app.route('/api/qa/save', methods=['POST'])
def force_save_qa():
    """强制保存QA数据（与自动保存一致，写回当前文件）"""
    try:
        success = candidate_qa_manager.export_final_results()
        return jsonify({'success': success, 'message': '已写回当前文件'})
    except Exception as e:
        return jsonify({'error': f'保存失败: {str(e)}'}), 500

@app.route('/api/qa/auto-save/toggle', methods=['POST'])
def toggle_auto_save():
    """切换自动保存状态"""
    try:
        data = request.json
        enabled = data.get('enabled', True)
        candidate_qa_manager.enable_auto_save(enabled)
        return jsonify({'success': True, 'auto_save_enabled': enabled})
    except Exception as e:
        return jsonify({'error': f'切换自动保存失败: {str(e)}'}), 500

@app.route('/api/qa/current-file')
def get_current_json_file():
    """获取当前JSON文件信息"""
    try:
        input_file = candidate_qa_manager.get_current_file()
        output_file = candidate_qa_manager.get_output_file()
        input_exists = os.path.exists(input_file) if input_file else False
        return jsonify({
            'input_file': input_file,
            'output_file': output_file,
            'file_name': (input_file.split('/')[-1] if input_file else ''),
            'exists': input_exists,
            'absolute_input_file': os.path.abspath(input_file) if input_file else '',
            'absolute_output_file': os.path.abspath(output_file) if output_file else ''
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 已移除列出 result 文件的接口，统一为单文件工作流

@app.route('/api/qa/list-data-files')
def list_data_files():
    """扫描data文件夹中的JSON文件"""
    try:
        data_dir = os.path.join(os.getcwd(), 'data')
        
        # 确保data文件夹存在
        if not os.path.exists(data_dir):
            os.makedirs(data_dir, exist_ok=True)
            return jsonify({'files': []})
        
        # 扫描JSON文件
        json_files = []
        for filename in os.listdir(data_dir):
            if filename.endswith('.json'):
                file_path = os.path.join(data_dir, filename)
                file_stat = os.stat(file_path)
                json_files.append({
                    'name': filename,
                    'path': file_path,
                    'absolute_path': os.path.abspath(file_path),
                    'size': file_stat.st_size,
                    'modified': file_stat.st_mtime
                })
        
        # 按修改时间排序（最新的在前）
        json_files.sort(key=lambda x: x['modified'], reverse=True)
        
        return jsonify({'files': json_files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/qa/load-data-file', methods=['POST'])
def load_data_file():
    """直接加载data文件夹中的JSON文件"""
    try:
        data = request.json
        file_name = data.get('file_name')
        
        if not file_name:
            return jsonify({'success': False, 'error': '未指定文件名'}), 400
        
        # 构建文件路径
        file_path = os.path.join(os.getcwd(), 'data', file_name)
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': f'文件不存在: {file_name}'}), 404
        
        # 读取文件内容
        with open(file_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # 重新加载候选QA管理器
        global candidate_qa_manager
        candidate_qa_manager = CandidateQAManager(file_path)
        
        return jsonify({
            'success': True,
            'message': f'成功加载文件: {file_name}',
            'file_name': file_name,
            'input_file': candidate_qa_manager.get_current_file(),
            'absolute_path': os.path.abspath(file_path)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/qa/load-file-by-path', methods=['POST'])
def load_file_by_path():
    """根据路径加载文件"""
    try:
        data = request.json
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({'success': False, 'error': '文件路径不能为空'}), 400
        
        if not os.path.exists(file_path):
            return jsonify({'success': False, 'error': '文件不存在'}), 404
        
        # 重新加载候选QA管理器
        global candidate_qa_manager
        candidate_qa_manager = CandidateQAManager(file_path)
        
        return jsonify({
            'success': True,
            'message': f'成功加载文件: {file_path}',
            'file_path': file_path,
            'file_name': os.path.basename(file_path)
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'加载文件失败: {str(e)}'}), 500

@app.route('/api/qa/load-json', methods=['POST'])
def load_json_file():
    """加载JSON文件作为输入文件"""
    try:
        data = request.json
        file_content = data.get('file_content')
        file_name = data.get('file_name', 'loaded_file.json')
        # 必须提供 file_path；若仅提供文件名，则在服务器上解析为已有同名文件路径
        file_path = data.get('file_path')
        if not file_path:
            return jsonify({'success': False, 'error': '未指定保存路径，已取消加载'}), 400
        
        # 使用用户指定的文件路径
        
        if not file_content:
            return jsonify({'success': False, 'error': '文件内容为空'}), 400
        
        # 解析JSON内容
        try:
            json_data = json.loads(file_content)
        except json.JSONDecodeError as e:
            return jsonify({'success': False, 'error': f'JSON格式错误: {str(e)}'}), 400
        
        # 使用用户指定的路径作为保存路径
        input_file_path = file_path
        
        # 确保目录存在
        os.makedirs(os.path.dirname(input_file_path), exist_ok=True)
        
        with open(input_file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
        
        # 重新加载候选QA管理器（输入文件）
        global candidate_qa_manager
        candidate_qa_manager = CandidateQAManager(input_file_path)
        
        return jsonify({
            'success': True, 
            'message': f'成功加载输入文件: {file_name}',
            'file_name': file_name,
            'input_file': candidate_qa_manager.get_current_file(),
            'output_file': candidate_qa_manager.get_output_file(),
            'absolute_path': os.path.abspath(input_file_path)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500



if __name__ == '__main__':
    print("=" * 60)
    print("🎬 SpatialBench 视频标注工具")
    print("=" * 60)
    print(f"🔧 调试模式: {'开启' if app.config['DEBUG'] else '关闭'}")
    print(f"🌐 访问地址: http://{app.config['HOST']}:{app.config['PORT']}")
    print(f"📁 数据目录: {app.config['DATA_DIR']}")
    print(f"🎥 视频目录: {app.config['VIDEO_DIR']}")
    print("=" * 60)
    
    logger.info("SpatialBench 应用启动")
    app.run(debug=app.config['DEBUG'], host=app.config['HOST'], port=app.config['PORT'])
