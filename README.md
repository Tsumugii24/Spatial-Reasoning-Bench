# SpatialBench 视频标注工具

## 🚀 快速开始

### 测试模式

```bash
# 1. 创建conda环境
mamba create -n benchannot python=3.12
mamba activate benchannot

# 2. 安装依赖
pip install -r requirements.txt

# 3. 启动应用
python app.py
```
- **访问地址**: http://localhost:5001

## 📊 数据下载与放置

请将带有"qacandidate"字样的json文件放置在该项目目录的`data/`文件夹下

请将视频的下载目录设置为根目录的`static/videos/` ，具体格式为 `static/videos/video名字的文件夹/*.mp4`

## 🎯 具体功能

- 输入 [http://127.0.0.1:5001](http://127.0.0.1:5001/) 后便可直接进入QA筛选界面
- 加载json：在左上角选择本次要打开的json文件（工具会自动识别`data`文件夹下的文件。您的所有修改将会自动同步至加载的json文件中）
- 选择segment：加载json后，页面左侧会加载出segment列表，您可以点击其中的segment项看到该segment所对应的QA Candidates
- 选择QA：页面中间是QA列表，您可以通过点击**"选择"**按钮来选中当前QA
- 观看片段：页面右侧是视频播放模块，在选择QA后，您可以选择播放QA对应的：
    - 完整片段 ：开始时间-结束时间
    - 前半段：开始时间-切分点
    - 后半段：切分点-结束时间
- 修改QA信息：根据上方的**QA筛选流程与准则**，您可以选择修改QA的相关信息、设置切分点、删除QA、标记是否可用（对于已标记可用的QA，工具会显示为浅绿色）

## 📝 数据收集

此后每一轮的数据收集，您只需要提交标注的JSON文件，其中直接存储了你标注的相关信息（例如是否选用等）

## 📁 项目结构

```
SpatialBench_Annotate/
├── app.py                    # 主应用
├── start.py                  # 生产环境启动脚本
├── config.py                 # 配置文件
├── models/                   # 数据模型
├── static/                   # 静态资源
├── templates/                # HTML模板
├── data/                     # JSON数据文件
└── requirements.txt          # 依赖包
```

## 🔧 环境要求

- Python 3.12+
- Conda/Mamba (推荐)
- FFmpeg (视频处理)
- 足够的存储空间用于视频文件

