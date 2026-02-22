# Spatial-Reasoning-Bench Video Labeling Tool

## 🚀 Quick Start

### Test Mode

```bash
# 1. Create conda environment
conda create -n bench python=3.12
conda activate bench

# 2. Install dependencies
pip install -r requirements.txt

# 3. Launch the application
python app.py
```
- **Access URL**: http://localhost:5001

## 📊 Data Download and Placement

Place JSON files containing "qacandidate" in the project's `data/` folder.

Set the video download directory to the root `static/videos/` folder. The expected format is `static/videos/<video_name_folder>/*.mp4`.

## 🎯 Features

- Enter [http://127.0.0.1:5001](http://127.0.0.1:5001/) to access the QA screening interface
- **Load JSON**: Select the JSON file to open from the top-left corner (the tool auto-detects files in the `data` folder; all changes are automatically synced to the loaded JSON file)
- **Select segment**: After loading a JSON, the segment list appears on the left. Click a segment to view its QA candidates
- **Select QA**: The QA list is in the center. Click the **"Select"** button to select the current QA
- **Watch clips**: The video player is on the right. After selecting a QA, you can play:
  - **Full clip**: Start time → End time
  - **First half**: Start time → Split point
  - **Second half**: Split point → End time
- **Edit QA info**: Following the **QA screening workflow and guidelines** above, you can edit QA details, set split points, delete QAs, or mark availability (available QAs are shown in green)

## 📝 Data Collection

For each round of data collection, submit only the annotated JSON file, which stores all annotation information directly.

## 🔧 Requirements

- Python 3.12
- FFmpeg
- Sufficient storage space for video downloads
