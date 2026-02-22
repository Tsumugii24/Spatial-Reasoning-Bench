"""
SpatialBench 视频标注工具 - 配置文件
"""

import os
from pathlib import Path

class Config:
    """基础配置"""
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'spatialbench-secret-key-2024'
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    HOST = os.environ.get('FLASK_HOST', '0.0.0.0')
    PORT = int(os.environ.get('FLASK_PORT', 5001))
    
    # 数据目录配置
    DATA_DIR = os.environ.get('DATA_DIR', 'data')
    VIDEO_DIR = os.environ.get('VIDEO_DIR', 'static/videos')
    QA_FILE_PATH = os.environ.get('QA_FILE_PATH', 'qa_results.json')
    
    # 视频下载配置
    MAX_VIDEO_SIZE = int(os.environ.get('MAX_VIDEO_SIZE', 500 * 1024 * 1024))  # 500MB
    DOWNLOAD_TIMEOUT = int(os.environ.get('DOWNLOAD_TIMEOUT', 300))  # 5分钟
    
    # HuggingFace配置
    HF_REPO = os.environ.get('HF_REPO', 'GuangsTrip/spatialpredictsource')
    HF_REPO_TYPE = os.environ.get('HF_REPO_TYPE', 'dataset')
    
    # 日志配置
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/spatialbench.log')
    
    # 安全配置
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    @staticmethod
    def init_app(app):
        """初始化应用配置"""
        # 创建必要的目录
        Path(Config.DATA_DIR).mkdir(exist_ok=True)
        Path(Config.VIDEO_DIR).mkdir(parents=True, exist_ok=True)
        Path('logs').mkdir(exist_ok=True)

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    LOG_LEVEL = 'WARNING'

class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    DEBUG = True
    DATA_DIR = 'test_data'

# 配置字典
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': ProductionConfig
}
