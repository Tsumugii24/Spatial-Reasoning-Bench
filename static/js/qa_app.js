// QA检查应用
class QAApp {
    constructor() {
        this.currentSegment = null;
        this.currentQAs = [];
        this.videoPlayer = null;
        this.selectedVideoFile = null;
        this.selectedQA = null;
        this.selectedForUseQAs = new Set();
        this.autoSaveTimers = new Map(); // 存储自动保存定时器
        this.autoSaveDelay = 500; // 0.5秒延迟自动保存（更快响应）
        this.currentVideoDirectory = 'static/videos'; // 固定视频目录
        this.autoSaveEnabled = true; // 自动保存已启用
        this.currentJSONFile = 'test_qacandidate_v1.json';
        this.currentPlayEndHandler = null; // 当前播放结束处理器
        this.init();
    }
    
    init() {
        this.videoPlayer = document.getElementById('videoPlayer');
        this.loadCurrentJSONFile();
        this.loadSegments();
        this.setupEventListeners();
        // 自动加载data文件夹中的文件列表
        this.loadDataFiles();
    }
    
    setupEventListeners() {
        // 视频播放器事件
        if (this.videoPlayer) {
            this.videoPlayer.addEventListener('loadedmetadata', () => {
                this.updateTimeDisplay();
            });
            
            this.videoPlayer.addEventListener('timeupdate', () => {
                this.updateTimeDisplay();
            });
        }
        
        // 键盘快捷键
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }
            
            switch(e.key) {
                case ' ':
                    e.preventDefault();
                    this.togglePlayPause();
                    break;
                case 'Enter':
                    e.preventDefault();
                    this.playSelectedQATime();
                    break;
            }
        });
    }
    
    async loadSegments() {
        try {
            this.showLoading(true);
            const response = await fetch('/api/qa/segments');
            const data = await response.json();
            
            if (data.segments) {
                this.renderSegments(data.segments);
                this.updateStatistics(data.segments);
            }
        } catch (error) {
            console.error('加载segments失败:', error);
            this.showError('加载segments失败');
        } finally {
            this.showLoading(false);
        }
    }
    
    renderSegments(segments) {
        const segmentList = document.getElementById('segmentList');
        if (!segmentList) return;
        segmentList.innerHTML = '';
        
        // 应用过滤器
        let filteredSegments = segments;
        if (this.currentFilter === 'all' || !this.currentFilter) {
            // 显示所有segment
            filteredSegments = segments;
        } else if (this.currentFilter === 'pending') {
            filteredSegments = segments.filter(segment => segment.state === 'generate sucess' || segment.state === 'pending' || segment.state === '待观察');
        } else if (this.currentFilter === 'selected') {
            filteredSegments = segments.filter(segment => segment.state === 'observed' || segment.state === 'selected' || segment.state === 'reviewed');
        } else if (this.currentFilter === 'unavailable') {
            filteredSegments = segments.filter(segment => segment.state === 'unavailable');
        }
        
        filteredSegments.forEach(segment => {
            const segmentElement = document.createElement('div');
            segmentElement.className = 'segment-item';
            segmentElement.setAttribute('data-segment-id', segment.id);
            
            // 确定segment状态
            let statusClass = 'unavailable';
            let statusText = '不可用';
            if (segment.state === 'generate sucess' || segment.state === 'pending' || segment.state === '待观察') {
                statusClass = 'pending';
                statusText = '待观察';
            } else if (segment.state === 'observed' || segment.state === 'selected' || segment.state === 'reviewed') {
                statusClass = 'reviewed';
                statusText = '已审阅';
            } else {
                statusClass = 'unavailable';
                statusText = '不可用';
            }
            
            // 先显示基本信息，视频名称稍后异步更新
            segmentElement.innerHTML = `
                <div class="segment-info">
                    <strong>${segment.id}</strong>
                    <div class="segment-status-section">
                        <label>状态:</label>
                        <select class="segment-status-select" onchange="qaApp.changeSegmentStatus('${segment.id}', this.value)">
                            <option value="unavailable" ${statusClass === 'unavailable' ? 'selected' : ''}>不可用</option>
                            <option value="pending" ${statusClass === 'pending' ? 'selected' : ''}>待观察</option>
                            <option value="reviewed" ${statusClass === 'reviewed' ? 'selected' : ''}>已审阅</option>
                        </select>
                    </div>
                    <div class="video-name-display">视频: 检测中...</div>
                    <div>QA数量: ${segment.qa_count}</div>
                    <div>最后修改: ${segment.last_modify}</div>
                </div>
            `;
            
            // 异步检测视频存在性并更新显示
            this.updateSegmentVideoName(segmentElement, segment);
            
            segmentElement.addEventListener('click', () => {
                this.selectSegment(segment.id);
            });
            
            segmentList.appendChild(segmentElement);
        });
    }
    
    async selectSegment(segmentId) {
        try {
            // 更新UI状态
            document.querySelectorAll('.segment-item').forEach(item => {
                item.classList.remove('active', 'loading', 'error');
            });
            
            // 如果之前有错误状态，清除它
            this.clearSegmentErrorStates();
            
            // 找到对应的segment元素并添加状态类
            const segmentElement = document.querySelector(`[data-segment-id="${segmentId}"]`);
            if (segmentElement) {
                segmentElement.classList.add('active', 'loading');
            }
            
            this.currentSegment = segmentId;
            const currentSegmentInfoEl = document.getElementById('currentSegmentInfo');
            if (currentSegmentInfoEl) {
                currentSegmentInfoEl.textContent = `当前: ${segmentId}`;
            }
            
            // 加载视频
            const videoLoaded = await this.loadVideoForSegment(segmentId);
            if (!videoLoaded) {
                // 标记为错误状态
                if (segmentElement) {
                    segmentElement.classList.remove('loading');
                    segmentElement.classList.add('error');
                }
                
                // 清空相关UI，避免产生加载成功的错觉
                this.clearUIOnError();
                
                this.showError('无法加载视频文件');
                return;
            }
            
            // 移除加载状态
            if (segmentElement) {
                segmentElement.classList.remove('loading');
            }
            
            // 加载QA数据
            this.showLoading(true);
            const response = await fetch(`/api/qa/segment/${segmentId}/qas`);
            const data = await response.json();
            
            if (data.qas) {
                this.currentQAs = data.qas;
                // 基于后端usable字段初始化前端选中集合
                this.selectedForUseQAs = new Set(
                    (data.qas || [])
                        .filter(q => q.usable === true)
                        .map(q => q.qa_id)
                );
                this.renderQAs(data.qas);
                const currentSegmentQAsEl = document.getElementById('currentSegmentQAs');
                if (currentSegmentQAsEl) {
                    currentSegmentQAsEl.textContent = data.qas.length;
                }
                
                // 更新可用QA统计
                this.updateSelectedForUseCount();
            }
        } catch (error) {
            console.error('加载QA失败:', error);
            this.showError('加载QA失败');
        } finally {
            this.showLoading(false);
        }
    }
    
    renderQAs(qas) {
        const qaList = document.getElementById('qaList');
        if (!qaList) return;
        qaList.innerHTML = '';
        
        qas.forEach((qa, index) => {
            // 确保QA有usable属性，如果没有则添加默认值false
            if (qa.usable === undefined) {
                qa.usable = false;
                // 自动保存这个默认值到后端
                this.autoSaveQA(qa.qa_id);
            }
            const qaElement = document.createElement('div');
            qaElement.className = 'qa-item';
            
            // 根据usable属性设置背景样式
            if (qa.usable === true) {
                qaElement.classList.add('selected-for-use');
            }
            qaElement.innerHTML = `
                <div class="qa-question">${qa.question || qa.Question || ''}</div>
                <div class="qa-answer"><strong>答案:</strong> ${qa.answer || qa.Answer || ''}</div>
                <div class="qa-meta">
                    <span>类型: ${qa.question_type || qa['Question Type'] || ''}</span> | 
                    <span>方向: ${this.getDirectionWithHint(qa.temporal_direction || qa['Temporal Direction'] || '')}</span> | 
                    <span>时间: ${this.ensureTimeFormat(qa.start_time || '00:00.00')} - ${this.ensureTimeFormat(qa.end_time || '00:10.00')}</span>
                </div>
                <div class="qa-cut-point-section">
                    <div class="qa-cut-point-display">
                        <label>切分点：</label>
                        <input type="text" id="cut_point_${qa.qa_id}" value="${qa.cut_point || '00:00'}" 
                               class="cut-point-input" placeholder="MM:SS" 
                               onchange="qaApp.updateCutPoint('${qa.qa_id}')">
                        <button class="btn btn-info btn-sm" onclick="qaApp.setCurrentTimeAsCutPoint('${qa.qa_id}')">
                            <i class="fas fa-clock"></i> 当前时间
                        </button>
                    </div>
                </div>
                <div class="qa-view-section">
                    <div class="qa-view-display">
                        <label>视角：</label>
                        <div class="viewpoint-input-group">
                            <input type="text" id="viewpoint_${qa.qa_id}" value="${qa['视角'] && qa['视角'].length > 0 ? qa['视角'].join(', ') : ''}" 
                                   class="viewpoint-input" placeholder="cam01.mp4,cam02.mp4" 
                                   onchange="qaApp.updateViewpoint('${qa.qa_id}')">
                            <button type="button" class="btn btn-sm btn-outline-success" onclick="qaApp.selectCurrentPerspective('${qa.qa_id}')" title="选择当前视角">
                                <i class="fas fa-plus"></i> 选择当前视角
                            </button>
                        </div>
                    </div>
                </div>
                <div class="qa-reason"><strong>推理:</strong> ${qa.reason || qa.Reason || ''}</div>
                <div class="qa-actions">
                    <button class="btn btn-primary btn-sm" onclick="qaApp.editQA('${qa.qa_id}')">
                        <i class="fas fa-edit"></i> 编辑
                    </button>
                    <button class="btn btn-danger btn-sm" onclick="qaApp.deleteQA('${qa.qa_id}')">
                        <i class="fas fa-trash"></i> 删除
                    </button>
                    <button class="btn btn-success btn-sm" onclick="qaApp.playQATime('${qa.start_time}', '${qa.end_time}')">
                        <i class="fas fa-play"></i> 播放
                    </button>
                    <button class="btn btn-info btn-sm" onclick="qaApp.selectQA('${qa.qa_id}')">
                        <i class="fas fa-hand-pointer"></i> 选择
                    </button>
                    <button class="btn ${qa.usable === true ? 'btn-danger' : 'btn-warning'} btn-sm" onclick="qaApp.toggleQAUsable('${qa.qa_id}')" id="useBtn_${qa.qa_id}">
                        <i class="fas ${qa.usable === true ? 'fa-times' : 'fa-check-circle'}"></i> ${qa.usable === true ? '标记不可用' : '标记可用'}
                    </button>
                </div>
                <div class="qa-edit-form" id="editForm_${qa.qa_id}">
                    <div class="form-group">
                        <label>问题:</label>
                        <textarea id="edit_question_${qa.qa_id}">${qa.question || qa.Question || ''}</textarea>
                    </div>
                    <div class="form-group">
                        <label>答案:</label>
                        <input type="text" id="edit_answer_${qa.qa_id}" value="${qa.answer || qa.Answer || ''}">
                    </div>
                    <div class="form-group">
                        <label>问题类型:</label>
                        <select id="edit_type_${qa.qa_id}">
                            <option value="Planning" ${(qa.question_type || qa['Question Type']) === 'Planning' ? 'selected' : ''}>Planning</option>
                            <option value="Relation" ${(qa.question_type || qa['Question Type']) === 'Relation' ? 'selected' : ''}>Relation</option>
                            <option value="Relative Distance" ${(qa.question_type || qa['Question Type']) === 'Relative Distance' ? 'selected' : ''}>Relative Distance</option>
                            <option value="Appearance Order" ${(qa.question_type || qa['Question Type']) === 'Appearance Order' ? 'selected' : ''}>Appearance Order</option>
                            <option value="Relative Size" ${(qa.question_type || qa['Question Type']) === 'Relative Size' ? 'selected' : ''}>Relative Size</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>时间方向:</label>
                        <select id="edit_direction_${qa.qa_id}">
                            <option value="Forward" ${(qa.temporal_direction || qa['Temporal Direction']) === 'Forward' ? 'selected' : ''}>Forward</option>
                            <option value="Backward" ${(qa.temporal_direction || qa['Temporal Direction']) === 'Backward' ? 'selected' : ''}>Backward</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>开始时间:</label>
                        <div class="time-input-group">
                            <input type="text" id="edit_start_time_${qa.qa_id}" value="${this.ensureTimeFormat(qa.start_time || '00:00.00')}" placeholder="MM:SS.SS">
                            <button type="button" class="btn btn-sm btn-outline-primary" onclick="qaApp.setCurrentTimeAsStartTime('${qa.qa_id}')" title="设置当前视频时间为开始时间">
                                <i class="fas fa-clock"></i> 当前时间
                            </button>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>结束时间:</label>
                        <div class="time-input-group">
                            <input type="text" id="edit_end_time_${qa.qa_id}" value="${this.ensureTimeFormat(qa.end_time || '00:10.00')}" placeholder="MM:SS.SS">
                            <button type="button" class="btn btn-sm btn-outline-primary" onclick="qaApp.setCurrentTimeAsEndTime('${qa.qa_id}')" title="设置当前视频时间为结束时间">
                                <i class="fas fa-clock"></i> 当前时间
                            </button>
                        </div>
                    </div>
                    <div class="form-group">
                        <label>推理:</label>
                        <textarea id="edit_reason_${qa.qa_id}">${qa.reason || qa.Reason || ''}</textarea>
                    </div>
                    <div class="qa-actions">
                        <button class="btn btn-success btn-sm" onclick="qaApp.saveQA('${qa.qa_id}')">
                            <i class="fas fa-save"></i> 保存
                        </button>
                        <button class="btn btn-warning btn-sm" onclick="qaApp.cancelEdit('${qa.qa_id}')">
                            <i class="fas fa-times"></i> 取消
                        </button>
                    </div>
                </div>
            `;
            
            qaList.appendChild(qaElement);
        });
    }
    
    editQA(qaId) {
        // 隐藏其他编辑表单
        document.querySelectorAll('.qa-edit-form').forEach(form => {
            form.style.display = 'none';
        });
        
        // 显示当前编辑表单
        const editForm = document.getElementById(`editForm_${qaId}`);
        editForm.style.display = 'block';
        
        // 标记为编辑状态
        editForm.closest('.qa-item').classList.add('editing');
        
        // 为编辑表单添加自动保存事件监听器
        this.setupAutoSaveListeners(qaId);
    }
    
    setupAutoSaveListeners(qaId) {
        const editForm = document.getElementById(`editForm_${qaId}`);
        if (!editForm) return;
        
        // 为所有输入字段添加自动保存监听器
        const inputs = editForm.querySelectorAll('input, textarea, select');
        inputs.forEach(input => {
            input.addEventListener('input', () => {
                this.scheduleQAAutoSave(qaId);
            });
        });
    }
    
    scheduleQAAutoSave(qaId) {
        const editForm = document.getElementById(`editForm_${qaId}`);
        if (!editForm) return;
        
        const updatedData = {
            Question: document.getElementById(`edit_question_${qaId}`).value,
            Answer: document.getElementById(`edit_answer_${qaId}`).value,
            'Question Type': document.getElementById(`edit_type_${qaId}`).value,
            'Temporal Direction': document.getElementById(`edit_direction_${qaId}`).value,
            start_time: document.getElementById(`edit_start_time_${qaId}`).value,
            end_time: document.getElementById(`edit_end_time_${qaId}`).value,
            Reason: document.getElementById(`edit_reason_${qaId}`).value
        };
        
        // 如果当前选中的QA有切分点，也保存切分点数据
        if (this.selectedQA && this.selectedQA.qa_id === qaId && this.selectedQA.cut_point) {
            updatedData.cut_point = this.selectedQA.cut_point;
        }
        
        this.scheduleAutoSave(qaId, updatedData, 'qa');
    }
    
    cancelEdit(qaId) {
        const editForm = document.getElementById(`editForm_${qaId}`);
        editForm.style.display = 'none';
        editForm.closest('.qa-item').classList.remove('editing');
    }
    
    async saveQA(qaId) {
        try {
            const updatedData = {
                question: document.getElementById(`edit_question_${qaId}`).value,
                answer: document.getElementById(`edit_answer_${qaId}`).value,
                question_type: document.getElementById(`edit_type_${qaId}`).value,
                temporal_direction: document.getElementById(`edit_direction_${qaId}`).value,
                start_time: document.getElementById(`edit_start_time_${qaId}`).value,
                end_time: document.getElementById(`edit_end_time_${qaId}`).value,
                reason: document.getElementById(`edit_reason_${qaId}`).value
            };
            
            // 如果当前选中的QA有切分点，也保存切分点数据
            if (this.selectedQA && this.selectedQA.qa_id === qaId && this.selectedQA.cutPoints) {
                updatedData.cutPoints = this.selectedQA.cutPoints;
            }
            
            const response = await fetch(`/api/qa/qa/${qaId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updatedData)
            });
            
            const result = await response.json();
            
            if (result.success) {
                // 更新本地数据
                const qaIndex = this.currentQAs.findIndex(qa => qa.qa_id === qaId);
                if (qaIndex !== -1) {
                    Object.assign(this.currentQAs[qaIndex], updatedData);
                }
                
                this.showSuccess('QA保存成功');
                this.cancelEdit(qaId);
                // 重新渲染QA列表以显示更新后的数据
                this.renderQAs(this.currentQAs);
                
                // 重新应用选中状态
                if (this.selectedQA && this.selectedQA.qa_id === qaId) {
                    this.selectQA(qaId);
                }
            } else {
                this.showError('保存失败');
            }
        } catch (error) {
            console.error('保存QA失败:', error);
            this.showError('保存QA失败');
        }
    }
    
    async deleteQA(qaId) {
        if (!confirm('确定要删除这个QA吗？')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/qa/qa/${qaId}`, {
                method: 'DELETE'
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess('QA删除成功');
                // 重新加载segment列表以更新QA数量
                await this.loadSegments();
                // 重新加载当前segment的QA
                if (this.currentSegment) {
                    this.selectSegment(this.currentSegment);
                }
            } else {
                this.showError('删除失败');
            }
        } catch (error) {
            console.error('删除QA失败:', error);
            this.showError('删除QA失败');
        }
    }
    
    playQATime(startTime, endTime) {
        if (!this.videoPlayer) return;
        
        console.log(`播放时间: ${startTime} - ${endTime}`);
        
        // 转换时间格式并播放（支持小数秒）
        const startSeconds = this.timeToSecondsWithDecimals(startTime);
        const endSeconds = this.timeToSecondsWithDecimals(endTime);
        
        // 设置视频源（这里需要根据实际的视频文件路径调整）
        if (!this.videoPlayer.src) {
            // 尝试从当前segment获取视频路径
            this.setVideoSource();
        }
        
        this.videoPlayer.currentTime = startSeconds;
        this.videoPlayer.play();
        
        // 清除之前的监听器
        if (this.currentPlayEndHandler) {
            this.videoPlayer.removeEventListener('timeupdate', this.currentPlayEndHandler);
        }
        
        // 设置高精度结束时间监听
        let animationId = null;
        const checkEndTime = () => {
            const currentTime = this.videoPlayer.currentTime;
            // 使用更精确的停止条件，允许0.05秒的误差
            if (currentTime >= endSeconds - 0.05) {
                // 精确设置到结束时间
                this.videoPlayer.currentTime = endSeconds;
                this.videoPlayer.pause();
                // 清除监听器和动画帧
                if (this.currentPlayEndHandler) {
                    this.videoPlayer.removeEventListener('timeupdate', this.currentPlayEndHandler);
                }
                if (animationId) {
                    cancelAnimationFrame(animationId);
                }
                this.currentPlayEndHandler = null;
                return;
            }
            // 继续检查
            animationId = requestAnimationFrame(checkEndTime);
        };
        
        // 使用timeupdate作为主要触发，requestAnimationFrame作为高精度检查
        this.currentPlayEndHandler = () => {
            if (this.videoPlayer.currentTime >= endSeconds - 0.1) {
                checkEndTime();
            }
        };
        
        this.videoPlayer.addEventListener('timeupdate', this.currentPlayEndHandler);
    }
    
    handleVideoFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            this.selectedVideoFile = file;
            const fileName = file.name;
            document.getElementById('selectedVideoName').textContent = fileName;
            
            // 创建视频URL并设置到播放器
            const videoURL = URL.createObjectURL(file);
            this.videoPlayer.src = videoURL;
            
            this.showSuccess(`已选择视频文件: ${fileName}`);
        }
    }
    
    async setVideoSource() {
        // 如果已经选择了视频文件，直接使用
        if (this.selectedVideoFile) {
            const videoURL = URL.createObjectURL(this.selectedVideoFile);
            this.videoPlayer.src = videoURL;
            return;
        }
        
        // 尝试自动调出本地视频
        if (this.currentSegment) {
            try {
                // 从当前segment的QA中获取视频源信息
                const qas = this.currentQAs;
                if (qas && qas.length > 0 && qas[0].video_source) {
                    const videoSource = qas[0].video_source;
                    console.log('尝试加载视频:', videoSource);
                    
                    // 尝试从当前视频根目录加载视频
                    const videoPath = `/${this.currentVideoDirectory.replace(/^[\/]/, '')}/${videoSource}`;
                    this.videoPlayer.src = videoPath;
                    
                    // 监听加载错误
                    this.videoPlayer.onerror = () => {
                        console.warn(`无法加载视频: ${videoPath}`);
                        this.showError(`无法自动加载视频: ${videoSource}`);
                    };
                    
                    // 监听加载成功
                    this.videoPlayer.onloadeddata = () => {
                        console.log('视频加载成功:', videoSource);
                        this.showSuccess(`已自动加载视频: ${videoSource}`);
                    };
                } else {
                    console.warn('未找到视频源信息');
                }
            } catch (error) {
                console.error('设置视频源失败:', error);
            }
        }
        
        // 更新视角选择器
        this.updateViewSelector();
    }
    
    updateViewSelector() {
        const viewSection = document.getElementById('viewSelectionSection');
        const viewButtons = document.getElementById('viewButtons');
        
        // 检查元素是否存在（因为视角选择区域可能不存在）
        if (!viewSection || !viewButtons) {
            return; // 如果元素不存在，直接返回
        }
        
        // 如果有选中的QA且有视角信息，显示视角选择器
        if (this.selectedQA && this.selectedQA['视角'] && this.selectedQA['视角'].length > 0) {
            viewSection.style.display = 'block';
            viewButtons.innerHTML = '';
            
            this.selectedQA['视角'].forEach((view, index) => {
                const viewBtn = document.createElement('button');
                viewBtn.className = 'view-btn';
                viewBtn.textContent = view;
                viewBtn.onclick = () => this.switchToView(view);
                
                if (index === 0) {
                    viewBtn.classList.add('active');
                    this.currentView = view;
                }
                
                viewButtons.appendChild(viewBtn);
            });
        } else {
            // 即使没有QA视角信息，也显示视角选择器（用于选择视角）
            viewSection.style.display = 'block';
            viewButtons.innerHTML = '<p style="color: #666; font-style: italic;">请先选择一个segment来加载视角信息</p>';
        }
    }
    
    async switchToView(viewName) {
        if (!this.selectedQA) return;
        
        // 更新当前视角
        this.currentView = viewName;
        
        // 更新按钮状态
        document.querySelectorAll('.view-btn').forEach(btn => {
            btn.classList.remove('active');
            if (btn.textContent === viewName) {
                btn.classList.add('active');
            }
        });
        
        // 尝试加载对应视角的视频
        await this.loadViewVideo(viewName);
        
        this.showSuccess(`已切换到视角: ${viewName}`);
    }
    
    async loadViewVideo(viewName) {
        // 获取当前视频名称，优先从选中的QA获取，否则从当前segment获取
        let videoName = 'default';
        
        if (this.selectedQA && this.selectedQA.video_source) {
            videoName = this.selectedQA.video_source.replace('.mp4', '');
        } else if (this.currentSegment) {
            // 尝试从当前segment的QA中获取视频名称
            const qas = this.currentQAs;
            if (qas && qas.length > 0 && qas[0].video_source) {
                videoName = qas[0].video_source.replace('.mp4', '');
            }
        }
        
        // 构建视角视频路径 - 使用后端API获取正确的路径
        let viewVideoPath;
        try {
            // 首先尝试从当前segment获取视频信息
            if (this.currentSegment) {
                const response = await fetch(`/api/qa/segment/${this.currentSegment}/video`);
                const data = await response.json();
                if (data.video_path) {
                    // 从现有路径中提取基础路径，然后替换视角
                    const basePath = data.video_path.substring(0, data.video_path.lastIndexOf('/'));
                    viewVideoPath = `${basePath}/${viewName}`;
                } else {
                    // 如果无法获取现有路径，使用统一默认路径: <base>/<video_name>/<perspective>
                    viewVideoPath = `/${this.currentVideoDirectory.replace(/^[\/]/, '')}/${videoName}/${viewName}`;
                }
            } else {
                // 如果没有当前segment，使用统一默认路径
                viewVideoPath = `/${this.currentVideoDirectory.replace(/^[\/]/, '')}/${videoName}/${viewName}`;
            }
        } catch (error) {
            console.warn('无法获取视频信息，使用默认路径:', error);
            viewVideoPath = `/${this.currentVideoDirectory.replace(/^[\/]/, '')}/${videoName}/${viewName}`;
        }
        
        console.log('尝试加载视角视频:', viewVideoPath);
        
        // 保存当前播放状态
        const currentTime = this.videoPlayer.currentTime;
        const wasPlaying = !this.videoPlayer.paused;
        
        // 清除之前的事件监听器
        this.videoPlayer.onerror = null;
        this.videoPlayer.onloadeddata = null;
        this.videoPlayer.onloadedmetadata = null;
        
        // 设置新的视频源
        this.videoPlayer.src = viewVideoPath;
        this.selectedVideoFile = viewVideoPath;
        
        // 强制加载视频
        this.videoPlayer.load();
        
        // 等待视频加载完成
        this.videoPlayer.onloadedmetadata = () => {
            console.log('视角视频元数据加载完成');
            // 恢复播放时间
            this.videoPlayer.currentTime = currentTime;
            
            // 如果之前在播放，继续播放
            if (wasPlaying) {
                this.videoPlayer.play().catch(e => {
                    console.warn('自动播放失败:', e);
                });
            }
            
            this.videoPlayer.onloadedmetadata = null; // 清除事件监听器
        };
        
        // 监听加载错误
        this.videoPlayer.onerror = (e) => {
            console.error('视角视频加载失败:', e);
            this.showError(`无法加载视角视频: ${viewName}`);
            this.videoPlayer.onerror = null;
        };
        
        // 监听加载成功
        this.videoPlayer.onloadeddata = () => {
            console.log('视角视频数据加载成功:', viewName);
            this.showSuccess(`已加载视角视频: ${viewName}`);
            this.videoPlayer.onloadeddata = null;
        };
    }
    
    playCurrentSegment() {
        if (!this.currentSegment || !this.videoPlayer) return;
        
        // 播放整个segment
        this.videoPlayer.play();
    }
    
    playSelectedQATime() {
        if (!this.selectedQA || !this.videoPlayer) {
            this.showError('请先选择一个QA');
            return;
        }
        
        if (!this.videoPlayer.src) {
            this.showError('请先选择视频文件');
            return;
        }
        
        const startTime = this.selectedQA.start_time;
        const endTime = this.selectedQA.end_time;
        
        if (!startTime || !endTime) {
            this.showError('QA时间信息不完整');
            return;
        }
        
        this.playQATime(startTime, endTime);
    }
    
    // 播放选中QA的前半段（开始时间到切分点）
    playSelectedQAFirstHalf() {
        if (!this.selectedQA || !this.videoPlayer) {
            this.showError('请先选择一个QA');
            return;
        }
        
        if (!this.videoPlayer.src) {
            this.showError('请先选择视频文件');
            return;
        }
        
        const startTime = this.selectedQA.start_time;
        const endTime = this.selectedQA.end_time;
        const cutPoint = this.selectedQA.cut_point;
        
        if (!startTime || !endTime) {
            this.showError('QA时间信息不完整');
            return;
        }
        
        if (!cutPoint) {
            this.showError('请先设置切分点');
            return;
        }
        
        // 验证切分点是否在开始-结束区间内
        const startSeconds = this.timeToSecondsWithDecimals(startTime);
        const endSeconds = this.timeToSecondsWithDecimals(endTime);
        const cutSeconds = this.timeToSecondsWithDecimals(cutPoint);
        
        if (cutSeconds < startSeconds || cutSeconds > endSeconds) {
            this.showError('切分点必须在开始时间和结束时间之间');
            return;
        }
        
        this.playQATime(startTime, cutPoint);
    }
    
    // 播放选中QA的后半段（切分点到结束时间）
    playSelectedQASecondHalf() {
        if (!this.selectedQA || !this.videoPlayer) {
            this.showError('请先选择一个QA');
            return;
        }
        
        if (!this.videoPlayer.src) {
            this.showError('请先选择视频文件');
            return;
        }
        
        const startTime = this.selectedQA.start_time;
        const endTime = this.selectedQA.end_time;
        const cutPoint = this.selectedQA.cut_point;
        
        if (!startTime || !endTime) {
            this.showError('QA时间信息不完整');
            return;
        }
        
        if (!cutPoint) {
            this.showError('请先设置切分点');
            return;
        }
        
        // 验证切分点是否在开始-结束区间内
        const startSeconds = this.timeToSecondsWithDecimals(startTime);
        const endSeconds = this.timeToSecondsWithDecimals(endTime);
        const cutSeconds = this.timeToSecondsWithDecimals(cutPoint);
        
        if (cutSeconds < startSeconds || cutSeconds > endSeconds) {
            this.showError('切分点必须在开始时间和结束时间之间');
            return;
        }
        
        this.playQATime(cutPoint, endTime);
    }
    
    timeToSeconds(timeStr) {
        // 将 MM:SS 格式转换为秒数
        const parts = timeStr.split(':');
        const minutes = parseInt(parts[0]);
        const seconds = parseInt(parts[1]);
        return minutes * 60 + seconds;
    }
    
    secondsToTime(seconds) {
        // 将秒数转换为 MM:SS 格式
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    
    updateTimeDisplay() {
        if (!this.videoPlayer) return;
        
        const current = this.secondsToTimeWithDecimals(this.videoPlayer.currentTime);
        const duration = this.secondsToTimeWithDecimals(this.videoPlayer.duration || 0);
        const currentTimeEl = document.getElementById('currentTime');
        if (currentTimeEl) {
            currentTimeEl.textContent = `${current} / ${duration}`;
        }
    }
    
    updateVideoPlayer() {
        if (!this.videoPlayer) return;
        
        // 清空视频源
        this.videoPlayer.src = '';
        this.videoPlayer.load();
        
        // 清空当前视频文件选择
        this.selectedVideoFile = null;
        
        // 重置时间显示
        const currentTimeEl = document.getElementById('currentTime');
        if (currentTimeEl) {
            currentTimeEl.textContent = '00:00 / 00:00';
        }
    }
    
    togglePlayPause() {
        if (!this.videoPlayer) return;
        
        if (this.videoPlayer.paused) {
            this.videoPlayer.play();
        } else {
            this.videoPlayer.pause();
        }
    }
    
    selectQA(qaId) {
        try {
            // 清除之前的选择
            document.querySelectorAll('.qa-item').forEach(item => {
                item.classList.remove('selected');
            });
            
            // 选择当前QA
            const qaElement = document.querySelector(`[onclick*="qaApp.selectQA('${qaId}')"]`).closest('.qa-item');
            if (qaElement) {
                qaElement.classList.add('selected');
            }
            
            // 找到对应的QA数据
            this.selectedQA = this.currentQAs.find(qa => qa.qa_id === qaId);
            
            if (this.selectedQA) {
                // 显示切分点控制
                this.updateCutPointUI();
                
                // 更新视角选择器
                this.updateViewSelector();
                
                // 更新当前视角显示和按钮状态
                this.updateCurrentPerspectiveDisplay(this.currentView);
            }
        } catch (error) {
            console.error('selectQA方法出错:', error);
            // 不显示错误提示，避免干扰用户
        }
    }
    
    updateCutPointUI() {
        const cutPointInfo = document.getElementById('cutPointInfo');
        const cutPointControls = document.getElementById('cutPointControls');
        
        // 检查元素是否存在（因为切分点控制区域可能不存在）
        if (!cutPointInfo || !cutPointControls) {
            return; // 如果元素不存在，直接返回
        }
        
        if (this.selectedQA) {
            const questionText = this.selectedQA.question || this.selectedQA.Question || '';
            cutPointInfo.innerHTML = `
                <div class="qa-title">当前QA: ${questionText.substring(0, 60)}...</div>
                <div>时间范围: ${this.ensureTimeFormat(this.selectedQA.start_time)} - ${this.ensureTimeFormat(this.selectedQA.end_time)}</div>
            `;
            cutPointControls.style.display = 'block';
            
            // 设置当前切分点值（如果输入框存在）
            const cutPointInput = document.getElementById('cutPointInput');
            if (cutPointInput) {
                cutPointInput.value = this.selectedQA.cut_point || '00:00';
            }
        } else {
            cutPointInfo.innerHTML = '<span class="text-muted">请先选择一个QA</span>';
            cutPointControls.style.display = 'none';
        }
    }
    
    selectPreviousQA() {
        if (!this.selectedQA || !this.currentQAs.length) return;
        
        const currentIndex = this.currentQAs.findIndex(qa => qa.qa_id === this.selectedQA.qa_id);
        if (currentIndex > 0) {
            const prevQA = this.currentQAs[currentIndex - 1];
            this.selectQA(prevQA.qa_id);
        }
    }
    
    selectNextQA() {
        if (!this.selectedQA || !this.currentQAs.length) return;
        
        const currentIndex = this.currentQAs.findIndex(qa => qa.qa_id === this.selectedQA.qa_id);
        if (currentIndex < this.currentQAs.length - 1) {
            const nextQA = this.currentQAs[currentIndex + 1];
            this.selectQA(nextQA.qa_id);
        }
    }
    
    // 切分点管理功能
    setCutPoint() {
        if (!this.selectedQA) {
            this.showError('请先选择一个QA');
            return;
        }
        
        const cutPointInput = document.getElementById('cutPointInput');
        const timeStr = cutPointInput.value.trim();
        
        if (!timeStr) {
            this.showError('请输入切分点时间');
            return;
        }
        
        // 验证时间格式（支持MM:SS.ss格式）
        if (!this.isValidTimeFormatWithDecimals(timeStr)) {
            this.showError('时间格式不正确，请使用MM:SS.ss格式');
            return;
        }
        
        const timeInSeconds = this.timeToSecondsWithDecimals(timeStr);
        
        // 检查时间是否在QA的时间范围内
        const startSeconds = this.timeToSecondsWithDecimals(this.selectedQA.start_time);
        const endSeconds = this.timeToSecondsWithDecimals(this.selectedQA.end_time);
        
        if (timeInSeconds < startSeconds || timeInSeconds > endSeconds) {
            this.showError(`切分点时间必须在QA时间范围内 (${this.ensureTimeFormat(this.selectedQA.start_time)} - ${this.ensureTimeFormat(this.selectedQA.end_time)})`);
            return;
        }
        
        // 设置切分点
        this.selectedQA.cut_point = timeStr;
        
        // 更新显示
        this.updateQAForUseDisplay(this.selectedQA.qa_id, this.selectedForUseQAs.has(this.selectedQA.qa_id));
        
        // 自动保存切分点
        this.scheduleCutPointAutoSave();
        
        this.showSuccess(`已设置切分点: ${timeStr}`);
    }
    
    scheduleCutPointAutoSave() {
        if (!this.selectedQA) return;
        
        const updatedData = {
            cut_point: this.selectedQA.cut_point
        };
        
        this.scheduleAutoSave(this.selectedQA.qa_id, updatedData, 'qa');
    }
    
    clearCutPoint() {
        if (!this.selectedQA) {
            this.showError('请先选择一个QA');
            return;
        }
        
        this.selectedQA.cut_point = null;
        document.getElementById('cutPointInput').value = '00:00';
        
        // 更新显示
        this.updateQAForUseDisplay(this.selectedQA.qa_id, this.selectedForUseQAs.has(this.selectedQA.qa_id));
        
        // 自动保存切分点清除
        this.scheduleCutPointAutoSave();
        
        this.showSuccess('已清除切分点');
    }
    
    jumpToCutPoint(timeInSeconds) {
        if (this.videoPlayer && this.videoPlayer.src) {
            this.videoPlayer.currentTime = timeInSeconds;
            this.showSuccess(`跳转到切分点: ${this.secondsToTimeWithDecimals(timeInSeconds)}`);
        } else {
            this.showError('请先选择视频文件');
        }
    }
    
    // 跳转到切分点（从输入框读取时间）
    jumpToCutPointFromInput() {
        if (!this.selectedQA) {
            this.showError('请先选择一个QA');
            return;
        }
        
        const cutPointInput = document.getElementById('cutPointInput');
        if (!cutPointInput || !cutPointInput.value.trim()) {
            this.showError('请输入切分点时间');
            return;
        }
        
        const timeStr = cutPointInput.value.trim();
        const timeInSeconds = this.timeToSecondsWithDecimals(timeStr);
        
        if (timeInSeconds === null) {
            this.showError('时间格式不正确，请使用 MM:SS.ss 格式');
            return;
        }
        
        if (this.videoPlayer && this.videoPlayer.src) {
            this.videoPlayer.currentTime = timeInSeconds;
            this.showSuccess(`跳转到切分点: ${timeStr}`);
        } else {
            this.showError('请先加载视频');
        }
    }
    
    isValidTimeFormat(timeStr) {
        const timeRegex = /^([0-5]?[0-9]):([0-5][0-9])$/;
        return timeRegex.test(timeStr);
    }
    
    isValidTimeFormatWithDecimals(timeStr) {
        const timeRegex = /^([0-5]?[0-9]):([0-5][0-9])(\.[0-9]{1,2})?$/;
        return timeRegex.test(timeStr);
    }
    
    timeToSecondsWithDecimals(timeStr) {
        // 将 MM:SS.ss 格式转换为秒数（支持小数）
        const parts = timeStr.split(':');
        const minutes = parseInt(parts[0]);
        const seconds = parseFloat(parts[1]); // 使用parseFloat支持小数
        return minutes * 60 + seconds;
    }
    
    secondsToTimeWithDecimals(seconds) {
        // 将秒数转换为 MM:SS.ss 格式（支持小数）
        const mins = Math.floor(seconds / 60);
        const secs = (seconds % 60).toFixed(2); // 保留两位小数
        return `${mins.toString().padStart(2, '0')}:${secs.padStart(5, '0')}`;
    }
    
    // 播放开始时间到切分点
    playStartToCut() {
        if (!this.selectedQA || !this.videoPlayer) {
            this.showError('请先选择一个QA和视频文件');
            return;
        }
        
        if (!this.selectedQA.cut_point) {
            this.showError('请先设置切分点');
            return;
        }
        
        const startSeconds = this.timeToSecondsWithDecimals(this.selectedQA.start_time);
        const cutSeconds = this.timeToSecondsWithDecimals(this.selectedQA.cut_point);
        
        this.videoPlayer.currentTime = startSeconds;
        this.videoPlayer.play();
        
        // 设置结束时间监听
        const checkEnd = () => {
            if (this.videoPlayer.currentTime >= cutSeconds) {
                this.videoPlayer.pause();
                this.videoPlayer.removeEventListener('timeupdate', checkEnd);
            }
        };
        
        this.videoPlayer.addEventListener('timeupdate', checkEnd);
        this.showSuccess(`播放开始时间到切分点: ${this.ensureTimeFormat(this.selectedQA.start_time)} - ${this.ensureTimeFormat(this.selectedQA.cut_point)}`);
    }
    
    // 播放切分点到结束时间
    playCutToEnd() {
        if (!this.selectedQA || !this.videoPlayer) {
            this.showError('请先选择一个QA和视频文件');
            return;
        }
        
        if (!this.selectedQA.cut_point) {
            this.showError('请先设置切分点');
            return;
        }
        
        const cutSeconds = this.timeToSecondsWithDecimals(this.selectedQA.cut_point);
        const endSeconds = this.timeToSecondsWithDecimals(this.selectedQA.end_time);
        
        this.videoPlayer.currentTime = cutSeconds;
        this.videoPlayer.play();
        
        // 设置结束时间监听
        const checkEnd = () => {
            if (this.videoPlayer.currentTime >= endSeconds) {
                this.videoPlayer.pause();
                this.videoPlayer.removeEventListener('timeupdate', checkEnd);
            }
        };
        
        this.videoPlayer.addEventListener('timeupdate', checkEnd);
        this.showSuccess(`播放切分点到结束时间: ${this.ensureTimeFormat(this.selectedQA.cut_point)} - ${this.ensureTimeFormat(this.selectedQA.end_time)}`);
    }
    
    // QA可用性标记功能
    toggleQAUsable(qaId) {
        if (this.selectedForUseQAs.has(qaId)) {
            this.selectedForUseQAs.delete(qaId);
            this.updateQAUsableDisplay(qaId, false);
            this.showSuccess('已标记QA为不可用');
        } else {
            this.selectedForUseQAs.add(qaId);
            this.updateQAUsableDisplay(qaId, true);
            this.showSuccess('已标记QA为可用');
        }
        
        // 持久化到后端JSON：更新对应QA的usable属性
        const qa = this.currentQAs.find(q => q.qa_id === qaId);
        if (qa) {
            qa.usable = this.selectedForUseQAs.has(qaId);
            this.autoSaveQA(qaId);
        }
    }
    
    // 不再使用localStorage保存/加载状态，状态来源于后端JSON中的usable字段
    
    updateQAUsableDisplay(qaId, isUsable) {
        const qaElement = document.querySelector(`[onclick*="qaApp.toggleQAUsable('${qaId}')"]`).closest('.qa-item');
        const useBtn = document.getElementById(`useBtn_${qaId}`);
        
        if (isUsable) {
            qaElement.classList.add('selected-for-use');
            useBtn.innerHTML = '<i class="fas fa-times"></i> 标记不可用';
            useBtn.className = 'btn btn-danger btn-sm';
        } else {
            qaElement.classList.remove('selected-for-use');
            useBtn.innerHTML = '<i class="fas fa-check-circle"></i> 标记可用';
            useBtn.className = 'btn btn-warning btn-sm';
        }
        
        // 更新统计信息
        this.updateSelectedForUseCount();
    }
    
    updateSelectedForUseCount() {
        const selectedForUseEl = document.getElementById('selectedForUseQAs');
        if (selectedForUseEl) {
            selectedForUseEl.textContent = this.selectedForUseQAs.size;
        }
    }
    
    // 自动保存功能 - 立即保存
    async scheduleAutoSave(qaId, data, type = 'qa') {
        // 立即执行保存，不使用延迟
        await this.performAutoSave(qaId, data, type);
    }
    
    async performAutoSave(qaId, data, type) {
        try {
            let url, method, payload;
            
            if (type === 'qa') {
                url = `/api/qa/qa/${qaId}`;
                method = 'PUT';
                payload = data;
            } else if (type === 'segment_status') {
                url = `/api/qa/segment/${qaId}/status`;
                method = 'POST';
                payload = { status: data };
            }
            
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });
            
            const result = await response.json();
            
            if (result.success) {
                console.log(`已自动保存: ${qaId}`);
                this.showAutoSaveIndicator();
            } else {
                console.error('自动保存失败:', result.error);
                this.showError(`保存失败: ${result.error}`);
            }
        } catch (error) {
            console.error('自动保存失败:', error);
            this.showError('保存失败，请检查网络连接');
        }
    }
    
    showAutoSaveIndicator() {
        // 显示自动保存指示器
        const indicator = document.createElement('div');
        indicator.className = 'auto-save-indicator';
        indicator.innerHTML = '<i class="fas fa-save"></i> 已自动保存';
        indicator.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: #28a745;
            color: white;
            padding: 8px 16px;
            border-radius: 4px;
            font-size: 12px;
            z-index: 1000;
            opacity: 0;
            transition: opacity 0.3s ease;
        `;
        
        document.body.appendChild(indicator);
        
        // 淡入效果
        setTimeout(() => {
            indicator.style.opacity = '1';
        }, 10);
        
        // 3秒后淡出并移除
        setTimeout(() => {
            indicator.style.opacity = '0';
            setTimeout(() => {
                if (indicator.parentNode) {
                    indicator.parentNode.removeChild(indicator);
                }
            }, 300);
        }, 3000);
    }
    
    // 清除segment错误状态
    clearSegmentErrorStates() {
        document.querySelectorAll('.segment-item.error').forEach(item => {
            item.classList.remove('error');
        });
    }
    
    // 当segment加载失败时清空相关UI
    clearUIOnError() {
        // 清空当前segment信息
        this.currentSegment = null;
        const currentSegmentInfoEl = document.getElementById('currentSegmentInfo');
        if (currentSegmentInfoEl) {
            currentSegmentInfoEl.textContent = '请选择segment';
        }
        
        // 清空QA列表
        this.currentQAs = [];
        this.selectedForUseQAs.clear();
        this.selectedQA = null;
        this.renderQAs([]);
        
        // 清空视频播放器
        if (this.videoPlayer) {
            this.videoPlayer.src = '';
            this.videoPlayer.poster = '';
        }
        this.selectedVideoFile = null;
        
        // 清空视频信息显示
        const videoInfo = document.getElementById('videoInfo');
        if (videoInfo) {
            videoInfo.innerHTML = '请选择segment加载视频';
        }
        
        // 重置时间显示
        const currentTimeEl = document.getElementById('currentTime');
        if (currentTimeEl) {
            currentTimeEl.textContent = '00:00 / 00:00';
        }
        
        // 隐藏视角选择区域
        const viewSection = document.getElementById('viewSelectionSection');
        if (viewSection) {
            viewSection.style.display = 'none';
        }
        
        // 清空视角按钮（在左侧面板中）
        const perspectiveButtons = document.getElementById('perspectiveButtons');
        if (perspectiveButtons) {
            perspectiveButtons.innerHTML = '';
        }
        
        // 清空切分点信息
        const cutPointInfo = document.getElementById('cutPointInfo');
        const cutPointControls = document.getElementById('cutPointControls');
        if (cutPointInfo) {
            cutPointInfo.innerHTML = '请先选择一个segment和QA';
        }
        if (cutPointControls) {
            cutPointControls.style.display = 'none';
        }
        
        // 更新统计信息
        this.updateSelectedForUseCount();
    }
    
    // Segment过滤功能
    showAllSegments() {
        this.currentFilter = 'all';
        this.loadSegments();
    }
    
    showPendingSegments() {
        this.currentFilter = 'pending';
        this.loadSegments();
    }
    
    showSelectedSegments() {
        this.currentFilter = 'selected';
        this.loadSegments();
    }
    
    showUnavailableSegments() {
        this.currentFilter = 'unavailable';
        this.loadSegments();
    }
    
    // 获取segment的视频名称（带存在性检测）
    async getSegmentVideoName(segment) {
        const videoName = segment.video_name || '未知视频';
        
        // 检测视频是否存在
        const videoExists = await this.checkVideoExists(segment);
        
        if (videoExists) {
            return videoName;
        } else {
            return `${videoName} (视频不存在)`;
        }
    }
    
    // 获取segment的视频名称（同步版本，用于不需要检测的情况）
    getSegmentVideoNameSync(segment) {
        return segment.video_name || '未知视频';
    }
    
    // 检测segment对应的视频是否存在
    async checkVideoExists(segment) {
        try {
            // 先尝试获取视频路径
            const response = await fetch(`/api/qa/segment/${segment.id}/video`);
            const data = await response.json();
            
            if (data.video_path) {
                // 使用HEAD请求检测视频文件是否存在
                const videoExists = await new Promise((resolve) => {
                    const xhr = new XMLHttpRequest();
                    xhr.open('HEAD', data.video_path, true);
                    xhr.timeout = 3000; // 3秒超时
                    
                    xhr.onload = () => {
                        // 检查状态码，200-299表示成功
                        resolve(xhr.status >= 200 && xhr.status < 300);
                    };
                    
                    xhr.onerror = () => resolve(false);
                    xhr.ontimeout = () => resolve(false);
                    
                    xhr.send();
                });
                
                return videoExists;
            }
            return false;
        } catch (error) {
            console.warn(`检测视频存在性失败: ${segment.id}`, error);
            return false;
        }
    }
    
    // 异步更新segment的视频名称显示
    async updateSegmentVideoName(segmentElement, segment) {
        try {
            const videoName = await this.getSegmentVideoName(segment);
            const videoNameDisplay = segmentElement.querySelector('.video-name-display');
            if (videoNameDisplay) {
                videoNameDisplay.textContent = `视频: ${videoName}`;
                
                // 如果视频不存在，添加相应的CSS类
                if (videoName.includes('(视频不存在)')) {
                    videoNameDisplay.classList.add('video-not-exists');
                } else {
                    videoNameDisplay.classList.remove('video-not-exists');
                }
            }
        } catch (error) {
            console.warn(`更新视频名称失败: ${segment.id}`, error);
            const videoNameDisplay = segmentElement.querySelector('.video-name-display');
            if (videoNameDisplay) {
                videoNameDisplay.textContent = `视频: ${segment.video_name || '未知视频'} (检测失败)`;
                videoNameDisplay.classList.add('video-not-exists');
            }
        }
    }
    
    // 获取带提示的方向文本
    getDirectionWithHint(direction) {
        if (!direction) {
            return '未知';
        }
        
        if (direction === 'Forward') {
            return 'Forward (前半段模型可见)';
        } else if (direction === 'Backward') {
            return 'Backward (后半段模型可见)';
        }
        
        return direction;
    }
    
    // 计算segment的时间范围
    calculateSegmentTimeRange(segment) {
        if (!segment.qas || segment.qas.length === 0) {
            return '00:00.00 - 00:00.00';
        }
        
        let minStartTime = null;
        let maxEndTime = null;
        
        segment.qas.forEach(qa => {
            const startTime = qa.start_time || '00:00.00';
            const endTime = qa.end_time || '00:00.00';
            
            // 确保时间格式为MM:SS.SS
            const formattedStartTime = this.ensureTimeFormat(startTime);
            const formattedEndTime = this.ensureTimeFormat(endTime);
            
            if (!minStartTime || formattedStartTime < minStartTime) {
                minStartTime = formattedStartTime;
            }
            if (!maxEndTime || formattedEndTime > maxEndTime) {
                maxEndTime = formattedEndTime;
            }
        });
        
        return `${minStartTime || '00:00.00'} - ${maxEndTime || '00:00.00'}`;
    }
    
    // 确保时间格式为MM:SS.SS
    ensureTimeFormat(timeStr) {
        if (!timeStr) return '00:00.00';
        
        // 如果已经是MM:SS.SS格式，直接返回
        if (timeStr.match(/^\d{2}:\d{2}\.\d{2}$/)) {
            return timeStr;
        }
        
        // 如果是MM:SS格式，添加.00
        if (timeStr.match(/^\d{2}:\d{2}$/)) {
            return timeStr + '.00';
        }
        
        // 如果是M:SS格式，补零
        if (timeStr.match(/^\d{1}:\d{2}$/)) {
            return '0' + timeStr + '.00';
        }
        
        // 如果是M:SS.S格式，补零
        if (timeStr.match(/^\d{1}:\d{2}\.\d{1}$/)) {
            return '0' + timeStr + '0';
        }
        
        // 默认返回00:00.00
        return '00:00.00';
    }
    
    // Segment状态管理
    changeSegmentStatus(segmentId, newStatus) {
        this.updateSegmentStatus(segmentId, newStatus);
    }
    
    async updateSegmentStatus(segmentId, newStatus) {
        try {
            const response = await fetch(`/api/qa/segment/${segmentId}/status`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ status: newStatus })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.showSuccess(`Segment状态已更新为: ${this.getStatusText(newStatus)}`);
                // 重新加载segments以显示更新后的状态
                this.loadSegments();
            } else {
                this.showError('更新状态失败');
            }
        } catch (error) {
            console.error('更新segment状态失败:', error);
            this.showError('更新状态失败');
        }
    }
    
    getStatusText(status) {
        const statusMap = {
            'unavailable': '不可用',
            'pending': '待观察',
            'generate sucess': '待观察',
            'reviewed': '已审阅',
            'selected': '已审阅',  // 兼容旧数据
            'observed': '已审阅',  // 兼容旧数据
            '待观察': '待观察'  // 处理中文状态值
        };
        return statusMap[status] || status;
    }
    
    async loadSegments(filterPending = false) {
        try {
            this.showLoading(true);
            const response = await fetch('/api/qa/segments');
            const data = await response.json();
            
            if (data.segments) {
                let segments = data.segments;
                
                // 如果过滤待观察的，只显示状态为'generate sucess'的
                if (filterPending) {
                    segments = segments.filter(segment => segment.state === 'generate sucess');
                }
                
                this.renderSegments(segments);
                this.updateStatistics(segments);
            }
        } catch (error) {
            console.error('加载segments失败:', error);
            this.showError('加载segments失败');
        } finally {
            this.showLoading(false);
        }
    }
    
    // 同步选用的QA到视频JSON文件
    async syncSelectedQAsToVideoJson() {
        if (!this.selectedVideoFile) {
            this.showError('请先选择视频文件');
            return;
        }
        
        if (this.selectedForUseQAs.size === 0) {
            this.showError('没有已审阅的QA');
            return;
        }
        
        try {
            const videoName = this.selectedVideoFile.name.replace(/\.[^/.]+$/, ""); // 移除扩展名
            const selectedQAs = this.currentQAs.filter(qa => this.selectedForUseQAs.has(qa.qa_id));
            
            const videoQAData = {
                video_name: videoName,
                video_file: this.selectedVideoFile.name,
                video_source: selectedQAs.length > 0 ? selectedQAs[0].video_source : null,
                sync_time: new Date().toISOString(),
                total_qas: selectedQAs.length,
                qas: selectedQAs.map(qa => ({
                    qa_id: qa.qa_id,
                    question: qa.Question,
                    answer: qa.Answer,
                    question_type: qa['Question Type'],
                    temporal_direction: qa['Temporal Direction'],
                    reason: qa.Reason,
                    start_time: qa.start_time,
                    end_time: qa.end_time,
                    cut_point: qa.cut_point,
                    segment_id: qa.segment_id,
                    video_source: qa.video_source
                }))
            };
            
            // 创建下载链接
            const dataStr = JSON.stringify(videoQAData, null, 2);
            const dataBlob = new Blob([dataStr], {type: 'application/json'});
            const url = URL.createObjectURL(dataBlob);
            
            // 创建下载链接
            const downloadLink = document.createElement('a');
            downloadLink.href = url;
            downloadLink.download = `${videoName}_qa_results.json`;
            document.body.appendChild(downloadLink);
            downloadLink.click();
            document.body.removeChild(downloadLink);
            URL.revokeObjectURL(url);
            
            this.showSuccess(`已导出 ${selectedQAs.length} 个已审阅的QA到 ${videoName}_qa_results.json`);
            
        } catch (error) {
            console.error('同步QA到视频JSON失败:', error);
            this.showError('同步失败');
        }
    }
    
    updateStatistics(segments) {
        const totalSegments = segments.length;
        const totalQAs = segments.reduce((sum, segment) => sum + segment.qa_count, 0);
        
        const totalSegmentsEl = document.getElementById('totalSegments');
        const totalQAsEl = document.getElementById('totalQAs');
        if (totalSegmentsEl) totalSegmentsEl.textContent = totalSegments;
        if (totalQAsEl) totalQAsEl.textContent = totalQAs;
    }
    
    showLoading(show) {
        const loadingEl = document.getElementById('loadingIndicator');
        if (loadingEl) {
            loadingEl.style.display = show ? 'flex' : 'none';
        }
    }
    
    showError(message) {
        alert(`错误: ${message}`);
    }
    
    showSuccess(message) {
        alert(`成功: ${message}`);
    }
    
    // 视频目录固定为 static/videos，无需动态选择
    
    async loadVideoForSegment(segmentId) {
        try {
            const response = await fetch(`/api/qa/segment/${segmentId}/video`);
            const data = await response.json();
            
            if (data.video_path) {
                // 测试视频文件是否可访问
                const videoLoaded = await new Promise((resolve) => {
                    const xhr = new XMLHttpRequest();
                    xhr.open('HEAD', data.video_path, true);
                    xhr.timeout = 3000; // 3秒超时
                    
                    xhr.onload = () => {
                        // 检查状态码，200-299表示成功
                        resolve(xhr.status >= 200 && xhr.status < 300);
                    };
                    
                    xhr.onerror = () => resolve(false);
                    xhr.ontimeout = () => resolve(false);
                    
                    xhr.send();
                });
                
                if (videoLoaded) {
                    this.videoPlayer.src = data.video_path;
                    this.selectedVideoFile = data.video_path;
                    
                    // 更新视频信息显示
                    const videoInfo = document.getElementById('videoInfo');
                    if (videoInfo) {
                        videoInfo.innerHTML = `
                            <strong>视频:</strong> ${data.video_name}<br>
                            <strong>类型:</strong> ${data.video_type}<br>
                            <strong>当前视角:</strong> ${data.current_perspective || 'N/A'}<br>
                            <strong>可用视角:</strong> ${data.available_perspectives.join(', ')}
                        `;
                    }
                    
                    // 更新视角按钮
                    this.updatePerspectiveButtons(data);
                    
                    // 显示视角选择区域
                    const viewSection = document.getElementById('viewSelectionSection');
                    if (viewSection) {
                        viewSection.style.display = 'block';
                    }
                    
                    return true;
                } else {
                    console.warn(`视频文件无法访问: ${data.video_path}`);
                    return false;
                }
            } else {
                console.warn('API返回的视频路径为空');
                return false;
            }
        } catch (error) {
            console.error('加载视频失败:', error);
            this.showError('加载视频失败');
            return false;
        }
    }
    
    updatePerspectiveButtons(videoData) {
        const perspectiveButtons = document.getElementById('perspectiveButtons');
        if (!perspectiveButtons) return;
        
        // 清空现有按钮
        perspectiveButtons.innerHTML = '';
        
        if (videoData.video_type === 'multi' && videoData.available_perspectives.length > 0) {
            // 显示视角按钮
            perspectiveButtons.style.display = 'block';
            
            videoData.available_perspectives.forEach(perspective => {
                const button = document.createElement('button');
                button.className = 'perspective-btn';
                button.textContent = perspective;
                
                // 如果是当前视角，标记为活跃
                if (perspective === videoData.current_perspective) {
                    button.classList.add('active');
                }
                
                // 添加点击事件
                button.onclick = (event) => this.switchPerspective(perspective, videoData.video_name, event.target);
                
                perspectiveButtons.appendChild(button);
            });
        } else {
            // 隐藏视角按钮
            perspectiveButtons.style.display = 'none';
        }
    }
    
    async switchPerspective(perspective, videoName, clickedButton = null) {
        try {
            // 更新按钮状态
            document.querySelectorAll('.perspective-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // 设置当前点击的按钮为active
            if (clickedButton) {
                clickedButton.classList.add('active');
            } else {
                // 如果没有传递按钮元素，尝试通过文本内容查找
                const button = Array.from(document.querySelectorAll('.perspective-btn')).find(btn => 
                    btn.textContent.trim() === perspective
                );
                if (button) {
                    button.classList.add('active');
                }
            }
            
            // 使用后端API获取正确的视频路径
            let videoPath;
            try {
                // 首先尝试从当前segment获取视频信息
                if (this.currentSegment) {
                    const response = await fetch(`/api/qa/segment/${this.currentSegment}/video`);
                    const data = await response.json();
                    if (data.video_path) {
                        // 从现有路径中提取基础路径，然后替换视角
                        const basePath = data.video_path.substring(0, data.video_path.lastIndexOf('/'));
                        videoPath = `${basePath}/${perspective}`;
                    } else {
                        // 如果无法获取现有路径，使用统一默认路径
                        videoPath = `/${this.currentVideoDirectory.replace(/^[\/]/, '')}/${videoName}/${perspective}`;
                    }
                } else {
                    // 如果没有当前segment，使用统一默认路径
                    videoPath = `/${this.currentVideoDirectory.replace(/^[\/]/, '')}/${videoName}/${perspective}`;
                }
            } catch (error) {
                console.warn('无法获取视频信息，使用默认路径:', error);
                videoPath = `/${this.currentVideoDirectory.replace(/^[\/]/, '')}/${videoName}/${perspective}`;
            }
            
            console.log('切换视角，视频路径:', videoPath);
            
            // 保存当前播放状态
            const currentTime = this.videoPlayer.currentTime;
            const wasPlaying = !this.videoPlayer.paused;
            
            // 清除之前的事件监听器
            this.videoPlayer.onerror = null;
            this.videoPlayer.onloadeddata = null;
            this.videoPlayer.onloadedmetadata = null;
            
            // 设置新的视频源
            this.videoPlayer.src = videoPath;
            this.selectedVideoFile = videoPath;
            
            // 强制加载视频
            this.videoPlayer.load();
            
            // 等待视频加载完成
            this.videoPlayer.onloadedmetadata = () => {
                console.log('视频元数据加载完成');
                // 恢复播放时间
                this.videoPlayer.currentTime = currentTime;
                
                // 如果之前在播放，继续播放
                if (wasPlaying) {
                    this.videoPlayer.play().catch(e => {
                        console.warn('自动播放失败:', e);
                    });
                }
                
                this.videoPlayer.onloadedmetadata = null; // 清除事件监听器
            };
            
            // 监听加载错误
            this.videoPlayer.onerror = (e) => {
                console.error('视频加载失败:', e);
                this.showError(`无法加载视角视频: ${perspective}`);
                this.videoPlayer.onerror = null;
            };
            
            // 监听加载成功
            this.videoPlayer.onloadeddata = () => {
                console.log('视频数据加载完成');
                this.videoPlayer.onloadeddata = null;
            };
            
            // 更新视频信息
            const videoInfo = document.getElementById('videoInfo');
            if (videoInfo) {
                const currentInfo = videoInfo.innerHTML;
                const updatedInfo = currentInfo.replace(
                    /<strong>当前视角:<\/strong> [^<]+/,
                    `<strong>当前视角:</strong> ${perspective}`
                );
                videoInfo.innerHTML = updatedInfo;
            }
            
            // 更新当前视角显示
            this.updateCurrentPerspectiveDisplay(perspective);
            
            // 更新当前视角到QA的视角属性中（如果当前有选中的QA）
            if (this.selectedQA) {
                this.updateQAPerspective(perspective);
            }
            
            this.showSuccess(`已切换到视角: ${perspective}`);
        } catch (error) {
            console.error('切换视角失败:', error);
            this.showError('切换视角失败');
        }
    }
    
    // JSON文件选择相关方法
    // selectJSONFile 方法已移除 - 现在使用data文件夹方案
    
    // 已移除 result 文件加载逻辑，统一为单文件工作流
    
    // 从指定路径加载文件
    async loadFileFromPath(filePath) {
        try {
            this.showLoading(true);
            
            const response = await fetch('/api/qa/load-file-by-path', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ file_path: filePath })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.currentJSONFile = result.file_path;
                const fileName = result.file_path.split('/').pop();
                const currentJSONFileEl = document.getElementById('currentJSONFile');
                const jsonFileDisplayEl = document.getElementById('jsonFileDisplay');
                if (currentJSONFileEl) {
                    currentJSONFileEl.innerHTML = `<small>当前文件: ${fileName}</small>`;
                }
                if (jsonFileDisplayEl) {
                    jsonFileDisplayEl.value = fileName;
                }
                
                this.showSuccess(`成功加载文件: ${fileName}`);
                
                // 重新加载segments
                await this.loadSegments();
                
                // 清空当前选择
                this.currentSegment = null;
                this.currentQAs = [];
                this.selectedQA = null;
                this.renderQAs([]);
                this.updateVideoPlayer();
            } else {
                this.showError(result.error || '加载文件失败');
            }
        } catch (error) {
            console.error('加载文件失败:', error);
            this.showError('加载文件失败: ' + error.message);
        } finally {
            this.showLoading(false);
        }
    }
    
    async loadCurrentJSONFile() {
        try {
            const response = await fetch('/api/qa/current-file');
            const data = await response.json();
            
            if (data.input_file && data.exists) {
                this.currentJSONFile = data.input_file;
                // 显示完整路径
                const currentJSONFileEl = document.getElementById('currentJSONFile');
                if (currentJSONFileEl) {
                    currentJSONFileEl.innerHTML = `<small>当前文件: ${data.absolute_input_file || data.input_file}</small>`;
                }
            } else {
                // 未设置当前文件时，提示用户选择
                const currentJSONFileEl = document.getElementById('currentJSONFile');
                if (currentJSONFileEl) currentJSONFileEl.innerHTML = `<small style="color:#888;">请先将JSON文件放在data文件夹中</small>`;
            }
        } catch (error) {
            console.error('加载当前JSON文件信息失败:', error);
        }
    }

    // 移除按路径加载功能 - 现在使用data文件夹方案
    
    async loadDataFiles() {
        try {
            this.showLoading(true);
            const response = await fetch('/api/qa/list-data-files');
            const data = await response.json();
            
            if (data.files) {
                this.renderDataFileList(data.files);
            } else {
                this.showError(data.error || '加载文件列表失败');
            }
        } catch (error) {
            console.error('加载data文件夹失败:', error);
            this.showError('加载文件列表失败: ' + error.message);
        } finally {
            this.showLoading(false);
        }
    }
    
    renderDataFileList(files) {
        const fileListEl = document.getElementById('dataFileList');
        const fileCountEl = document.getElementById('fileCount');
        if (!fileListEl) return;
        
        // 更新文件计数
        if (fileCountEl) {
            fileCountEl.textContent = `${files.length} 个文件`;
        }
        
        if (files.length === 0) {
            fileListEl.innerHTML = '<div style="text-align: center; color: #888; padding: 15px; font-size: 12px;">data文件夹中没有JSON文件</div>';
            return;
        }
        
        let html = '';
        files.forEach(file => {
            const fileSize = (file.size / 1024).toFixed(1) + 'KB';
            const modifiedDate = new Date(file.modified * 1000).toLocaleDateString();
            
            html += `
                <div class="data-file-item" style="padding: 4px 6px; border-bottom: 1px solid #e9ecef; cursor: pointer; display: flex; justify-content: space-between; align-items: center; font-size: 12px; transition: background-color 0.2s;" 
                     onmouseover="this.style.backgroundColor='#e9ecef'" 
                     onmouseout="this.style.backgroundColor='transparent'"
                     onclick="qaApp.selectDataFile('${file.name}')">
                    <div style="flex: 1; min-width: 0;">
                        <div style="font-weight: 500; color: #333; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${file.name}">${file.name}</div>
                        <div style="font-size: 11px; color: #6c757d;">${fileSize} • ${modifiedDate}</div>
                    </div>
                    <button onclick="event.stopPropagation(); qaApp.selectDataFile('${file.name}')" 
                            style="padding: 2px 6px; background: #28a745; color: white; border: none; border-radius: 2px; cursor: pointer; font-size: 11px; margin-left: 8px; flex-shrink: 0;">
                        选择
                    </button>
                </div>
            `;
        });
        
        fileListEl.innerHTML = html;
    }
    
    toggleFileList() {
        const fileListEl = document.getElementById('dataFileList');
        const toggleBtn = document.getElementById('toggleFileListBtn');
        
        if (!fileListEl || !toggleBtn) return;
        
        const isVisible = fileListEl.style.display !== 'none';
        
        if (isVisible) {
            fileListEl.style.display = 'none';
            toggleBtn.innerHTML = '<i class="fas fa-chevron-down"></i> 展开文件列表';
            toggleBtn.style.background = '#6c757d';
        } else {
            fileListEl.style.display = 'block';
            toggleBtn.innerHTML = '<i class="fas fa-chevron-up"></i> 收起文件列表';
            toggleBtn.style.background = '#495057';
        }
    }
    
    async selectDataFile(fileName) {
        try {
            this.showLoading(true);
            
            const response = await fetch('/api/qa/load-data-file', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    file_name: fileName
                })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.currentJSONFile = result.input_file;
                
                // 显示当前文件信息
                const currentJSONFileEl = document.getElementById('currentJSONFile');
                if (currentJSONFileEl) {
                    currentJSONFileEl.innerHTML = `<small>当前文件: ${result.absolute_path}</small>`;
                }
                
                this.showSuccess(result.message);
                
                // 重新加载segments
                await this.loadSegments();
                
                // 清空当前选择
                this.currentSegment = null;
                this.currentQAs = [];
                this.selectedQA = null;
                this.renderQAs([]);
                this.updateVideoPlayer();
            } else {
                this.showError(result.error || '加载文件失败');
            }
            
        } catch (error) {
            console.error('加载data文件失败:', error);
            this.showError('加载文件失败: ' + error.message);
        } finally {
            this.showLoading(false);
        }
    }
    
    readFileAsText(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = e => resolve(e.target.result);
            reader.onerror = e => reject(e);
            reader.readAsText(file);
        });
    }
    
    // Cut Point 相关方法
    updateCutPoint(qaId) {
        const cutPointInput = document.getElementById(`cut_point_${qaId}`);
        const cutPoint = cutPointInput.value;
        
        // 找到对应的QA并更新
        const qa = this.currentQAs.find(q => q.qa_id === qaId);
        if (qa) {
            qa.cut_point = cutPoint;
            this.autoSaveQA(qaId);
        }
    }
    
    setCurrentTimeAsCutPoint(qaId) {
        if (this.videoPlayer) {
            const currentTime = this.videoPlayer.currentTime;
            const minutes = Math.floor(currentTime / 60);
            const seconds = (currentTime % 60).toFixed(2);
            const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.padStart(5, '0')}`;
            
            const cutPointInput = document.getElementById(`cut_point_${qaId}`);
            cutPointInput.value = timeString;
            
            // 更新QA数据
            const qa = this.currentQAs.find(q => q.qa_id === qaId);
            if (qa) {
                qa.cut_point = timeString;
                this.autoSaveQA(qaId);
            }
            
            this.showSuccess(`切分点已设置为: ${timeString}`);
        } else {
            this.showError('请先加载视频');
        }
    }
    
    // 为当前选中的QA设置当前时间为切分点
    setCurrentTimeAsCutPointForSelected() {
        if (!this.selectedQA) {
            this.showError('请先选择一个QA');
            return;
        }
        
        if (this.videoPlayer) {
            const currentTime = this.videoPlayer.currentTime;
            const minutes = Math.floor(currentTime / 60);
            const seconds = (currentTime % 60).toFixed(2);
            const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.padStart(5, '0')}`;
            
            // 更新切分点输入框
            const cutPointInput = document.getElementById('cutPointInput');
            if (cutPointInput) {
                cutPointInput.value = timeString;
            }
            
            // 更新QA数据
            this.selectedQA.cut_point = timeString;
            this.autoSaveQA(this.selectedQA.qa_id);
            
            this.showSuccess(`已设置切分点为: ${timeString}`);
        } else {
            this.showError('视频播放器未加载');
        }
    }
    
    // 设置当前视频时间为开始时间
    setCurrentTimeAsStartTime(qaId) {
        if (this.videoPlayer) {
            const currentTime = this.videoPlayer.currentTime;
            const minutes = Math.floor(currentTime / 60);
            const seconds = (currentTime % 60).toFixed(2);
            const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.padStart(5, '0')}`;
            
            // 更新开始时间输入框
            const startTimeInput = document.getElementById(`edit_start_time_${qaId}`);
            if (startTimeInput) {
                startTimeInput.value = timeString;
            }
            
            // 更新QA数据
            const qa = this.currentQAs.find(q => q.qa_id === qaId);
            if (qa) {
                qa.start_time = timeString;
                this.autoSaveQA(qaId);
            }
            
            this.showSuccess(`开始时间已设置为: ${timeString}`);
        } else {
            this.showError('请先加载视频');
        }
    }
    
    // 设置当前视频时间为结束时间
    setCurrentTimeAsEndTime(qaId) {
        if (this.videoPlayer) {
            const currentTime = this.videoPlayer.currentTime;
            const minutes = Math.floor(currentTime / 60);
            const seconds = (currentTime % 60).toFixed(2);
            const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.padStart(5, '0')}`;
            
            // 更新结束时间输入框
            const endTimeInput = document.getElementById(`edit_end_time_${qaId}`);
            if (endTimeInput) {
                endTimeInput.value = timeString;
            }
            
            // 更新QA数据
            const qa = this.currentQAs.find(q => q.qa_id === qaId);
            if (qa) {
                qa.end_time = timeString;
                this.autoSaveQA(qaId);
            }
            
            this.showSuccess(`结束时间已设置为: ${timeString}`);
        } else {
            this.showError('请先加载视频');
        }
    }
    
    // 更新QA的视角属性
    updateQAPerspective(perspective) {
        if (!this.selectedQA) return;
        
        // 更新QA数据中的视角
        if (!this.selectedQA['视角']) {
            this.selectedQA['视角'] = [];
        }
        
        // 如果视角不在列表中，添加到列表中
        if (!this.selectedQA['视角'].includes(perspective)) {
            this.selectedQA['视角'].push(perspective);
        }
        
        // 更新视角输入框
        const viewpointInput = document.getElementById(`viewpoint_${this.selectedQA.qa_id}`);
        if (viewpointInput) {
            viewpointInput.value = this.selectedQA['视角'].join(', ');
        }
        
        // 自动保存
        this.autoSaveQA(this.selectedQA.qa_id);
        
        this.showSuccess(`已将视角 ${perspective} 添加到QA中`);
    }
    
    // 更新当前视角显示
    updateCurrentPerspectiveDisplay(perspective) {
        const currentPerspectiveDisplay = document.getElementById('currentPerspectiveDisplay');
        const selectCurrentPerspectiveBtn = document.getElementById('selectCurrentPerspectiveBtn');
        
        if (currentPerspectiveDisplay) {
            currentPerspectiveDisplay.textContent = perspective || '未选择';
        }
        
        // 如果有选中的QA，显示选择按钮
        if (selectCurrentPerspectiveBtn) {
            selectCurrentPerspectiveBtn.style.display = this.selectedQA ? 'inline-block' : 'none';
        }
    }
    
    // 选择当前视角到QA（新函数，用于按钮点击）
    selectCurrentPerspectiveForQA() {
        if (!this.selectedQA) {
            this.showError('请先选择一个QA');
            return;
        }
        
        // 获取当前选中的视角
        const activeButton = document.querySelector('.perspective-btn.active');
        if (!activeButton) {
            this.showError('请先选择一个视角');
            return;
        }
        
        const currentPerspective = activeButton.textContent.trim();
        
        // 更新QA数据中的视角
        if (!this.selectedQA['视角']) {
            this.selectedQA['视角'] = [];
        }
        
        // 如果视角不在列表中，添加到列表中
        if (!this.selectedQA['视角'].includes(currentPerspective)) {
            this.selectedQA['视角'].push(currentPerspective);
        }
        
        // 更新视角输入框
        const viewpointInput = document.getElementById(`viewpoint_${this.selectedQA.qa_id}`);
        if (viewpointInput) {
            viewpointInput.value = this.selectedQA['视角'].join(', ');
        }
        
        // 自动保存
        this.autoSaveQA(this.selectedQA.qa_id);
        
        this.showSuccess(`已将视角 ${currentPerspective} 添加到QA中`);
    }
    
    // 选择当前视角（原有函数，保持兼容性）
    selectCurrentPerspective(qaId) {
        // 获取当前选中的视角
        const activeButton = document.querySelector('.perspective-btn.active');
        if (!activeButton) {
            this.showError('请先选择一个视角');
            return;
        }
        
        const currentPerspective = activeButton.textContent.trim();
        
        // 更新QA数据中的视角
        const qa = this.currentQAs.find(q => q.qa_id === qaId);
        if (!qa) {
            this.showError('找不到对应的QA');
            return;
        }
        
        if (!qa['视角']) {
            qa['视角'] = [];
        }
        
        // 如果视角不在列表中，添加到列表中
        if (!qa['视角'].includes(currentPerspective)) {
            qa['视角'].push(currentPerspective);
        }
        
        // 更新视角输入框
        const viewpointInput = document.getElementById(`viewpoint_${qaId}`);
        if (viewpointInput) {
            viewpointInput.value = qa['视角'].join(', ');
        }
        
        // 自动保存
        this.autoSaveQA(qaId);
        
        this.showSuccess(`已将视角 ${currentPerspective} 添加到QA中`);
    }
    
    updateViewpoint(qaId) {
        const viewpointInput = document.getElementById(`viewpoint_${qaId}`);
        const viewpointText = viewpointInput.value;
        
        // 将逗号分隔的字符串转换为数组
        const viewpoints = viewpointText.split(',').map(v => v.trim()).filter(v => v);
        
        // 找到对应的QA并更新
        const qa = this.currentQAs.find(q => q.qa_id === qaId);
        if (qa) {
            qa['视角'] = viewpoints;
            this.autoSaveQA(qaId);
        }
    }
    
    // 自动保存QA数据
    async autoSaveQA(qaId) {
        try {
            const qa = this.currentQAs.find(q => q.qa_id === qaId);
            if (!qa) return;
            
            const response = await fetch(`/api/qa/qa/${qaId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(qa)
            });
            
            if (response.ok) {
                console.log(`QA ${qaId} 自动保存成功`);
            } else {
                console.error(`QA ${qaId} 自动保存失败`);
            }
        } catch (error) {
            console.error('自动保存QA失败:', error);
        }
    }
}

// 全局函数，供HTML调用

// 初始化应用
const qaApp = new QAApp();
