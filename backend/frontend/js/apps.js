// ============================================================
// 应用窗口
// ============================================================

// ===== 工具函数 =====
function escapeHtml(s) {
  if (typeof s !== 'string') return '';
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function fmtDate(d) {
  if (!d) return '';
  return new Date(d).toLocaleDateString('zh-CN');
}

// ===== 1. 主页概览（实时项目统计） =====
function openOverview() {
  var html =
    '<div style="margin-bottom:12px"><span class="text-success">●</span> 系统正常运行</div>' +
    '<div id="overviewStats" style="text-align:center;padding:20px 0;color:#666">加载中...</div>';
  var win = WinMgr.create('📊 主页概览', html, 500, 280, 'overview_win');

  api.get('/projects').then(function(data) {
    var projects = data.projects || [];
    var totalCh = 0;
    var recent = '';
    projects.forEach(function(p) { totalCh += (p.chapter_count || 0); });
    // 最近活动：找 updated_at 最近的项目
    var sorted = projects.slice().sort(function(a, b) {
      return new Date(b.updated_at || 0) - new Date(a.updated_at || 0);
    });
    if (sorted.length > 0 && sorted[0].updated_at) {
      recent = fmtDate(sorted[0].updated_at) + ' — ' + sorted[0].title;
    } else {
      recent = '暂无活动';
    }

    var statsEl = win.el.querySelector('#overviewStats');
    if (statsEl) {
      statsEl.innerHTML =
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;text-align:left;">' +
          '<div style="background:#111;border:1px solid #333;padding:10px;">' +
            '<div style="color:#888;font-size:11px;">项目总数</div>' +
            '<div style="color:#0f0;font-size:24px;font-weight:700;">' + projects.length + '</div>' +
          '</div>' +
          '<div style="background:#111;border:1px solid #333;padding:10px;">' +
            '<div style="color:#888;font-size:11px;">章节总数</div>' +
            '<div style="color:#ffb86b;font-size:24px;font-weight:700;">' + totalCh + '</div>' +
          '</div>' +
        '</div>' +
        '<div style="margin-top:10px;color:#888;text-align:left;">' +
          '<div style="margin-top:4px;">📌 最近活动：' + escapeHtml(recent) + '</div>' +
        '</div>' +
        '<div style="margin-top:12px;color:#666;font-size:11px;">💡 点击左侧「项目与写作」管理项目</div>';
    }
  }).catch(function() {
    var statsEl = win.el.querySelector('#overviewStats');
    if (statsEl) statsEl.innerHTML = '<div class="text-error">加载失败</div>';
  });
}

// ===== 2. 项目列表 =====
var currentProjectId = null;

function openProjectList() {
  var win = WinMgr.create('📚 项目列表', '<div class="project-list-loading" style="text-align:center;padding:40px 0;color:#666">加载中...</div>', 700, 480, 'projectlist_win');
  renderProjectList(win);
}

async function renderProjectList(win) {
  var body = win.el.querySelector('.win-body');
  if (!body) return;

  var projects;
  try {
    var data = await api.get('/projects');
    projects = data.projects || [];
  } catch (err) {
    body.innerHTML = '<div class="text-error">加载失败: ' + escapeHtml(err.message) + '</div>';
    return;
  }

  if (!currentProjectId || !projects.find(function(p) { return p.id === currentProjectId; })) {
    currentProjectId = projects.length > 0 ? projects[0].id : null;
  }

  var html =
    '<div class="project-list-layout">' +
      '<div class="project-tabs" id="projectTabs">' +
        projects.map(function(p) {
          return '<div class="tab-item' + (p.id === currentProjectId ? ' active' : '') + '" data-id="' + p.id + '">' + escapeHtml(p.title) + '</div>';
        }).join('') +
        '<div class="tab-item" id="newProjectBtn" style="color:#0f0;border-left-color:#0f0;">➕ 新建项目</div>' +
      '</div>' +
      '<div class="project-detail" id="projectDetail">' +
        '<div class="detail-row"><label>📖 书名</label><input type="text" id="projTitle" style="width:100%;" /></div>' +
        '<div class="detail-row"><label>✍️ 作者</label><input type="text" id="projAuthor" style="width:100%;" /></div>' +
        '<div class="detail-row"><label>📝 大纲（无字数限制）</label><textarea id="projOutline" style="width:100%;min-height:100px;"></textarea></div>' +
        '<div class="detail-row"><label>🌍 设定（无字数限制）</label><textarea id="projSetting" style="width:100%;min-height:100px;"></textarea></div>' +
        '<div style="display:flex;gap:8px;">' +
          '<div class="detail-row" style="flex:1;"><label>📄 每章字数</label><input type="number" id="projWordsPerChapter" style="width:100%;" /></div>' +
          '<div class="detail-row" style="flex:1;"><label>📚 预计总章节</label><input type="number" id="projExpectedChapters" style="width:100%;" /></div>' +
        '</div>' +
        '<div style="margin-top:8px;">' +
          '<button class="btn btn-primary" id="saveProjectBtn">💾 保存</button>' +
          '<button class="btn btn-danger" id="deleteProjectBtn" style="margin-left:6px;">🗑️ 删除</button>' +
          '<button class="btn btn-primary" id="exportProjectBtn" style="margin-left:6px;">📥 导出</button>' +
          '<button class="btn btn-primary" id="importProjectBtn" style="margin-left:6px;">📤 导入</button>' +
          '<input type="file" accept=".epub" id="importFileInput" style="display:none" />' +
          '<button class="btn btn-primary" id="goWritingBtn" style="float:right;">✍️ 写作</button>' +
        '</div>' +

        '<span id="projectFeedback" style="color:#0f0;margin-left:4px;margin-top:4px;display:block;"></span>' +
      '</div>' +
    '</div>';

  body.innerHTML = html;

  var tabs = body.querySelectorAll('.tab-item');
  var projTitle = body.querySelector('#projTitle');
  var projAuthor = body.querySelector('#projAuthor');
  var projOutline = body.querySelector('#projOutline');
  var projSetting = body.querySelector('#projSetting');
  var projWordsPerChapter = body.querySelector('#projWordsPerChapter');
  var projExpectedChapters = body.querySelector('#projExpectedChapters');
  var feedback = body.querySelector('#projectFeedback');

  function loadProjectDetail(projectId) {
    var p = null;
    for (var i = 0; i < projects.length; i++) {
      if (projects[i].id === projectId) { p = projects[i]; break; }
    }
    if (!p) return;
    projTitle.value = p.title || '';
    projAuthor.value = p.author || '';
    projOutline.value = p.outline || '';
    projSetting.value = p.setting || '';
    projWordsPerChapter.value = p.words_per_chapter || '';
    projExpectedChapters.value = p.expected_chapters || '';
    tabs.forEach(function(t) { t.classList.remove('active'); });
    tabs.forEach(function(t) { if (t.dataset.id === projectId) t.classList.add('active'); });
    currentProjectId = projectId;
  }

  function refreshTabs() {
    renderProjectList(win);
  }

  // tab 点击
  tabs.forEach(function(tab) {
    tab.onclick = function() {
      if (this.id === 'newProjectBtn') {
        this.textContent = '⏳ 创建中...';
        api.post('/projects', { title: '新项目', author: '匿名' }).then(function(data) {
          currentProjectId = data.id || data.project?.id;
          if (feedback) feedback.textContent = '✅ 已创建';
          window.uiLog('info', '新项目已创建');
          refreshTabs();
        }).catch(function(err) {
          if (feedback) feedback.textContent = '❌ ' + err.message;
          window.uiLog('error', '创建项目失败: ' + err.message);
        });
        return;
      }
      var id = this.dataset.id;
      if (id) {
        currentProjectId = id;
        loadProjectDetail(id);
      }
    };
  });

  // 保存（显示状态，不重置窗口）
  body.querySelector('#saveProjectBtn').onclick = function() {
    if (!currentProjectId) { feedback.textContent = '⚠️ 未选择项目'; return; }
    var btn = this;
    var orig = btn.textContent;
    btn.textContent = '⏳ 保存中...';
    btn.disabled = true;
    var titleVal = projTitle.value.trim() || '未命名';
    api.patch('/projects/' + currentProjectId, {
      title: titleVal,
      author: projAuthor.value.trim() || '匿名',
      outline: projOutline.value,
      setting: projSetting.value,
      words_per_chapter: parseInt(projWordsPerChapter.value) || 0,
      expected_chapters: parseInt(projExpectedChapters.value) || 0,
    }).then(function() {
      feedback.textContent = '✅ 已保存';
      window.uiLog('info', '项目「' + titleVal + '」已保存');
      var activeTab = body.querySelector('.tab-item.active');
      if (activeTab) activeTab.textContent = titleVal;
      projects.some(function(p) {
        if (p.id === currentProjectId) { p.title = titleVal; p.author = projAuthor.value.trim(); p.outline = projOutline.value; p.setting = projSetting.value; p.words_per_chapter = parseInt(projWordsPerChapter.value) || 0; p.expected_chapters = parseInt(projExpectedChapters.value) || 0; return true; }
      });
    }).catch(function(err) {
      feedback.textContent = '❌ ' + err.message;
      window.uiLog('error', '保存失败: ' + err.message);
    }).finally(function() {
      btn.textContent = orig;
      btn.disabled = false;
      setTimeout(function() { if (feedback.textContent.startsWith('✅')) feedback.textContent = ''; }, 3000);
    });
  };

  // 删除
  body.querySelector('#deleteProjectBtn').onclick = function() {
    if (!currentProjectId) { feedback.textContent = '⚠️ 未选择项目'; return; }
    if (!confirm('确定删除当前项目吗？')) return;
    var btn = this;
    btn.textContent = '⏳ 删除中...';
    btn.disabled = true;
    api.del('/projects/' + currentProjectId).then(function() {
      feedback.textContent = '✅ 已删除';
      window.uiLog('info', '项目已删除');
      currentProjectId = null;
      refreshTabs();
    }).catch(function(err) {
      feedback.textContent = '❌ ' + err.message;
      window.uiLog('error', '删除失败: ' + err.message);
    }).finally(function() {
      btn.textContent = '🗑️ 删除';
      btn.disabled = false;
    });
  };

  // 导出
  body.querySelector('#exportProjectBtn').onclick = function() {
    if (!currentProjectId) return;
    var project = null;
    for (var i = 0; i < projects.length; i++) {
      if (projects[i].id === currentProjectId) { project = projects[i]; break; }
    }
    if (!project) return;
    api.request('GET', '/projects/' + currentProjectId + '/export', null, { raw: true })
      .then(function(r) { return r.blob(); })
      .then(function(blob) {
        var url = URL.createObjectURL(new Blob([blob], { type: 'application/epub+zip' }));
        var a = document.createElement('a');
        a.href = url;
        a.download = (project.title || 'project') + '.epub';
        a.click();
        URL.revokeObjectURL(url);
        feedback.textContent = '✅ 导出成功';
      }).catch(function(err) {
        feedback.textContent = '❌ ' + err.message;
      });
  };

  // 导入
  body.querySelector('#importProjectBtn').onclick = function() {
    body.querySelector('#importFileInput').click();
  };
  body.querySelector('#importFileInput').onchange = function(e) {
    var file = e.target.files[0];
    if (!file) return;
    var fd = new FormData();
    fd.append('file', file);
    api.upload('/projects/import', fd).then(function() {
      feedback.textContent = '✅ 导入成功';
      refreshTabs();
    }).catch(function(err) {
      feedback.textContent = '❌ ' + err.message;
    });
    e.target.value = '';
  };

  // 写作
  body.querySelector('#goWritingBtn').onclick = function() {
    if (!currentProjectId) return;
    openWriterWorkspace(currentProjectId);
  };

  if (currentProjectId) loadProjectDetail(currentProjectId);
}

// ===== 全局自动完本状态 =====
var _stopAutoComplete = false;

// ===== 合并 thinking + ai → 单个 assistant（多轮对话必须） =====
function buildChatMessages(history) {
    var out = [];
    var pending = null;
    for (var i = 0; i < history.length; i++) {
      var m = history[i];
      if (m.role === 'tool_call') {
        // Convert completed tool_call to assistant.tool_calls + tool result messages
        if (m.status === 'done' && m.result !== null) {
          var tcId = m.tool_call_id || 'call_' + i;
          // Merge preceding thinking into assistant message
          out.push({
            role: 'assistant',
            content: pending || null,
            tool_calls: [{
              id: tcId,
              type: 'function',
              function: { name: m.name, arguments: m.arguments }
            }]
          });
          out.push({ role: 'tool', tool_call_id: tcId, content: m.result });
          pending = null;
        } // else: pending tool_call, skip
      } else if (m.role === 'tool_result') {
        continue; // Already handled via tool_call conversion
      } else if (m.role === 'thinking') {
        pending = (pending || '') + m.content;
      } else if (m.role === 'ai') {
        out.push({ role: 'assistant', content: pending ? pending + '\n\n' + m.content : m.content });
        pending = null;
      } else {
        if (pending) { out.push({ role: 'assistant', content: pending }); pending = null; }
        out.push({ role: m.role, content: m.content });
      }
    }
    if (pending) out.push({ role: 'assistant', content: pending });
    return out;
}

// ===== 共享流式聊天方法 =====
function safeCall(fn /*, args... */) {
  if (typeof fn !== 'function') return;
  var args = Array.prototype.slice.call(arguments, 1);
  try { fn.apply(null, args); } catch(e) { /* swallow callback errors */ }
}

async function streamChat(messages, onThinking, onContent, onError, onDone, onStatus, projectId, onToolEvent, chapterId) {
  var doneCalled = false;
  function finish() { if (!doneCalled) { doneCalled = true; safeCall(onDone); } }
  function status(text) { if (typeof onStatus === 'function') safeCall(onStatus, text); }

  var streamId = null;
  try {
    status('⏳ 提交请求...');
    var reqBody = {
      messages: messages,
      model: window.getSetting('model') || 'deepseek-v4-flash-free',
      thinking: true,
      stream: true,
      api_key: window.getSetting('apiKey') || undefined,
      api_base: window.getSetting('apiEndpoint') || undefined,
    };
    if (projectId) reqBody.project_id = projectId;
    if (chapterId) reqBody.chapter_id = chapterId;
    var data = await api.post('/write/async', reqBody);
    streamId = data.stream_id;
    if (!streamId) { safeCall(onError, '未获取到 stream_id'); finish(); return; }
  } catch (e) {
    safeCall(onError, '提交请求失败: ' + e.message);
    finish(); return;
  }

  var lastSeq = -1;
  var pollCount = 0;
  var doneHash = null;

  function poll() {
    var url = '/write/recover/' + streamId + '?since=' + lastSeq;
    api.get(url).then(function(data) {
      pollCount = 0;

      if (data.events && data.events.length > 0) {
        for (var i = 0; i < data.events.length; i++) {
          var e = data.events[i];
          if (e.seq > lastSeq) lastSeq = e.seq;
          if (e.type === 'thinking' && e.data.reasoning) safeCall(onThinking, e.data.reasoning);
          if (e.type === 'content' && e.data.content) safeCall(onContent, e.data.content);
          if (e.type === 'tool_status' && e.data.name) {
            status('🛠️ ' + e.data.name + '...');
            if (typeof onToolEvent === 'function') safeCall(onToolEvent, e);
          }
          if (e.type === 'tool_result' && e.data.name) {
            if (typeof onToolEvent === 'function') safeCall(onToolEvent, e);
          }
          if (e.type === 'error' && e.data.error) { safeCall(onError, e.data.error); finish(); return; }
        }
      }

      if (data.status === 'done') {
        doneHash = data.content_hash;
        status('✅ 完成 (校验: ' + doneHash + ')');
        finish();
        return;
      }
      if (data.status === 'error') {
        safeCall(onError, data.error || '处理失败');
        finish();
        return;
      }

      status('⏳ 处理中...');
      setTimeout(poll, 300);
    }).catch(function(err) {
      var delay = Math.min(1000 + pollCount * 200, 5000);
      status('⚠️ 断联重试 (' + (pollCount + 1) + ')...');
      pollCount++;
      if (pollCount < 60) { setTimeout(poll, delay); return; }
      safeCall(onError, '轮询超时: ' + err.message);
      finish();
    });
  }

  status('⏳ 处理中...');
  poll();
}

// ===== 3. 写作工作区 =====
function openWriterWorkspace(projectId) {
  var winId = 'writer_win_' + projectId;
  // 如果已打开则聚焦
  var existing = WinMgr.find(winId);
  if (existing) { WinMgr.focus(winId); return; }

  var win = WinMgr.create('✍️ 写作工作区', '<div style="text-align:center;padding:40px 0;color:#666">加载中...</div>', 1100, 650, winId);
  loadWriterWorkspace(win, projectId);
}

async function loadWriterWorkspace(win, projectId) {
  var body = win.el.querySelector('.win-body');
  if (!body) return;

  var project, chapters;
  try {
    var projData = await api.get('/projects/' + projectId);
    project = projData;
    var chData = await api.get('/projects/' + projectId + '/chapters');
    chapters = chData.chapters || [];
  } catch (err) {
    body.innerHTML = '<div class="text-error">加载失败: ' + escapeHtml(err.message) + '</div>';
    return;
  }

  if (!chapters || chapters.length === 0) {
    try {
      var newCh = await api.post('/projects/' + projectId + '/chapters', { title: '第一章', content: '' });
      chapters = [newCh];
    } catch (err) {
      body.innerHTML = '<div class="text-error">创建章节失败: ' + escapeHtml(err.message) + '</div>';
      return;
    }
  }

  var currentChapterId = chapters[0].id;
  var currentChapter = chapters[0];

  var html =
    '<div class="writer-layout">' +
      '<div class="writer-chapters" id="chaptersList">' +
        chapters.map(function(c) {
          return '<div class="ch-item' + (c.id === currentChapterId ? ' active' : '') + '" data-id="' + c.id + '">' +
            '<span class="ch-title-text">' + escapeHtml(c.title) + '</span>' +
            '<input class="ch-title-input" type="text" value="' + escapeHtml(c.title) + '" />' +
            '<span class="ch-edit-icon">✎</span>' +
            '<span class="ch-delete-icon" title="删除章节">✕</span>' +
          '</div>';
        }).join('') +
        '<div class="new-ch-btn" id="newChapterBtn">➕ 新建章节</div>' +
        '<div class="new-ch-btn" id="autoCompleteBtn" style="border-color:#a855f7;color:#a855f7;">🚀 自动完本</div>' +
        '<span id="autoCompleteStatus" style="font-size:11px;color:#888;padding:2px 8px;display:none;"></span>' +
      '</div>' +
      '<div class="writer-main">' +
        '<div class="top-info">' +
          '<span class="title">📖 ' + escapeHtml(project.title) + '</span>' +
          '<span class="chapter-num" id="chapterNum"></span>' +
          '<span class="chapter-title-display" id="chapterTitleDisplay"></span>' +
          '<input class="chapter-title-input" type="text" id="chapterTitleInput" />' +
        '</div>' +
        '<div class="editor-wrap">' +
          '<div class="editor-toolbar"><span id="saveStatus" style="color:#888;font-size:11px;"></span>' +
            '<button id="saveBtn" style="margin-left:auto;font-size:11px;padding:1px 8px;">💾 保存</button>' +
          '</div>' +
          '<textarea id="editorContent" spellcheck="false"></textarea>' +
        '</div>' +
      '</div>' +
      '<div class="writer-right">' +
        '<div class="chat-history" id="chatHistory"></div>' +
        '<div class="chat-input-area">' +
          '<input type="text" id="chatInput" placeholder="输入指令..." />' +
          '<button id="sendBtn">发送</button>' +
          '<button id="fillBtn" class="fill-btn">📥 填入</button>' +
          '<button id="clearChatBtn" class="fill-btn" style="margin-left:4px;">🗑️ 清空</button>' +
          '<button id="memoriesBtn" class="memories-btn" style="margin-left:4px;font-size:12px;padding:2px 6px;">📖 记忆</button>' +
          '<button id="prepareChapterBtn" class="prepare-btn">📝 准备新章节</button>' +
          '<button id="stopAutoCompleteBtn" style="display:none;margin-left:4px;border-color:#f55;color:#f55;">⏹ 停止</button>' +
        '</div>' +
      '</div>' +
    '</div>';

  body.innerHTML = html;

  var chaptersContainer = body.querySelector('#chaptersList');
  var editor = body.querySelector('#editorContent');
  var chatHistory = body.querySelector('#chatHistory');
  var chatInput = body.querySelector('#chatInput');
  var sendBtn = body.querySelector('#sendBtn');
  var fillBtn = body.querySelector('#fillBtn');
  var newChapterBtn = body.querySelector('#newChapterBtn');
  var prepareBtn = body.querySelector('#prepareChapterBtn');
  var memoriesBtn = body.querySelector('#memoriesBtn');
  var clearChatBtn = body.querySelector('#clearChatBtn');
  var stopAutoBtn = body.querySelector('#stopAutoCompleteBtn');
  var chapterNumDisplay = body.querySelector('#chapterNum');
  stopAutoBtn.onclick = function() { _stopAutoComplete = true; stopAutoBtn.style.display = 'none'; };

  async function startAutoComplete() {
    // Re-query elements inside chaptersContainer (fresh after each refreshChapterList)
    var acBtn = chaptersContainer.querySelector('#autoCompleteBtn');
    var acStatus = chaptersContainer.querySelector('#autoCompleteStatus');
    if (!acBtn || !acStatus) return;
    if (_stopAutoComplete) return;
    var p = null;
    try { p = await api.get('/projects/' + projectId); } catch(e) { alert('❌ ' + e.message); return; }
    var total = p.expected_chapters || 0;
    if (total <= 0) { alert('⚠️ 请先设置预计总章节数'); return; }
    if (chapters.length >= total) { alert('✅ 已达到目标章节数'); return; }
    if (!confirm('将从第 ' + (chapters.length + 1) + ' 章自动写到第 ' + total + ' 章（共 ' + (total - chapters.length) + ' 章），是否继续？')) return;
    _stopAutoComplete = false;
    stopAutoBtn.style.display = 'inline-block';
    acBtn.style.display = 'none';
    acStatus.style.display = 'block';
    try {
      while (chapters.length < total) {
        if (_stopAutoComplete) {
          acStatus.textContent = '⏹ 已停止（完成 ' + chapters.length + '/' + total + ' 章）';
          break;
        }
        acStatus.textContent = '🔄 正在写第 ' + (chapters.length + 1) + '/' + total + ' 章...';
        var newCh = await api.post('/projects/' + projectId + '/chapters', { title: '第 ' + (chapters.length + 1) + ' 章', content: '' });
        await refreshChapterList();
        var chItem = chaptersContainer.querySelector('.ch-item[data-id="' + newCh.id + '"]');
        if (chItem) { chItem.click(); }
        await new Promise(function(r) { setTimeout(r, 400); });
        if (_stopAutoComplete) break;
        if (typeof prepareBtn.onclick === 'function') {
          await prepareBtn.onclick();
        } else {
          acStatus.textContent = '❌ 出错: 准备按钮未就绪';
          break;
        }
        if (_stopAutoComplete) break;
        autoFillFromAI();
        await new Promise(function(r) { setTimeout(r, 400); });
        // Re-query acStatus after refresh (chaptersContainer was re-rendered)
        acStatus = chaptersContainer.querySelector('#autoCompleteStatus');
      }
      if (!_stopAutoComplete && chapters.length >= total) {
        acStatus = chaptersContainer.querySelector('#autoCompleteStatus');
        acStatus.textContent = '🎉 自动完本完成！共 ' + total + ' 章';
      }
    } catch(e) {
      var s = chaptersContainer.querySelector('#autoCompleteStatus');
      if (s) s.textContent = '❌ 出错: ' + e.message;
    } finally {
      stopAutoBtn.style.display = 'none';
      acBtn = chaptersContainer.querySelector('#autoCompleteBtn');
      if (acBtn) acBtn.style.display = '';
    }
  }
  var chapterTitleDisplay = body.querySelector('#chapterTitleDisplay');
  var chapterTitleInput = body.querySelector('#chapterTitleInput');

  var saveTimer = null;
  var chatSaveTimer = null;
  var sendingInProgress = false;
  var chatKey = 'proj_' + projectId + '_ch_' + currentChapterId;
  var currentChatHistory = [];

  function chatKeyFor(projId, chId) { return 'proj_' + projId + '_ch_' + chId; }

  async function loadChatHistory(projId, chId) {
    var key = chatKeyFor(projId, chId);
    try {
      var data = await api.get('/chat/' + key);
      return data.messages || [];
    } catch(e) { return []; }
  }

  function debouncedSaveHistory() {
    if (chatSaveTimer) clearTimeout(chatSaveTimer);
    chatSaveTimer = setTimeout(function() {
      var key = chatKeyFor(projectId, currentChapterId);
      api.put('/chat/' + key, { messages: currentChatHistory }).catch(function(){});
    }, 1500);
  }

  async function saveChatHistory(projId, chId, history) {
    var key = chatKeyFor(projId, chId);
    try { await api.put('/chat/' + key, { messages: history }); } catch(e) {}
  }

  var chatRenderedCount = 0;

  function renderChat() {
    while (chatRenderedCount < currentChatHistory.length) {
      var msg = currentChatHistory[chatRenderedCount];
      if (!msg) { chatRenderedCount++; continue; }
      var div = document.createElement('div');
      if (msg.role === 'tool_call') {
        div.className = 'chat-msg tool-call';
        var argsHtml = '<span style="color:#58a6ff;">' + escapeHtml(msg.arguments) + '</span>';
        var resultHtml = msg.status === 'done' && msg.result
          ? '<br><span style="color:#3fb950;">→ ' + escapeHtml(msg.result) + '</span>'
          : ' <span style="color:#888;">⏳</span>';
        div.innerHTML = '<span style="color:#888;">🛠️ ' + escapeHtml(msg.name) + '</span> ' + argsHtml + resultHtml;
      } else {
        div.className = 'chat-msg ' + (msg.role === 'thinking' ? 'thinking' : msg.role);
        if (msg.role === 'thinking') {
          div.textContent = '🤔 ' + msg.content;
        } else if (msg.role === 'user') {
          div.textContent = '👤 ' + msg.content;
        } else {
          div.textContent = '🤖 ' + msg.content;
        }
      }
      chatHistory.appendChild(div);
      chatRenderedCount++;
    }
    if (chatRenderedCount > 0) {
      var lastMsg = currentChatHistory[chatRenderedCount - 1];
      var lastEl = chatHistory.lastElementChild;
      if (lastEl && lastMsg) {
        if (lastMsg.role === 'tool_call') {
          var argsHtml = '<span style="color:#58a6ff;">' + escapeHtml(lastMsg.arguments) + '</span>';
          var resultHtml = lastMsg.status === 'done' && lastMsg.result
            ? '<br><span style="color:#3fb950;">→ ' + escapeHtml(lastMsg.result) + '</span>'
            : ' <span style="color:#888;">⏳</span>';
          lastEl.innerHTML = '<span style="color:#888;">🛠️ ' + escapeHtml(lastMsg.name) + '</span> ' + argsHtml + resultHtml;
        } else if (lastMsg.role !== 'user') {
          lastEl.textContent = (lastMsg.role === 'thinking' ? '🤔 ' : '🤖 ') + lastMsg.content;
        }
      }
    }
    chatHistory.scrollTop = chatHistory.scrollHeight;
  }

  async function loadChapterContent(chapterId) {
    var ch = null;
    for (var i = 0; i < chapters.length; i++) {
      if (chapters[i].id === chapterId) { ch = chapters[i]; break; }
    }
    if (!ch) return;

    var idx = chapters.indexOf(ch);
    currentChapterId = chapterId;
    currentChapter = ch;
    chatKey = chatKeyFor(projectId, chapterId);

    editor.value = ch.content || '';
    chapterNumDisplay.textContent = '第 ' + (idx + 1) + ' 章';
    chapterTitleDisplay.textContent = ch.title;
    chapterTitleInput.value = ch.title;

    // 高亮列表
    chaptersContainer.querySelectorAll('.ch-item').forEach(function(item) {
      item.classList.toggle('active', item.dataset.id === chapterId);
      if (item.dataset.id === chapterId) {
        var ts = item.querySelector('.ch-title-text');
        var ti = item.querySelector('.ch-title-input');
        if (ts) ts.textContent = ch.title;
        if (ti) ti.value = ch.title;
      }
    });

    // 更新标题
    WinMgr.find(win.id).title = '✍️ ' + project.title + ' - ' + ch.title;
    win.el.querySelector('.win-title').textContent = '✍️ ' + project.title + ' - ' + ch.title;

    // 加载聊天（清空旧消息、重置计数器，避免越界）
    currentChatHistory = await loadChatHistory(projectId, chapterId);
    chatHistory.innerHTML = '';
    chatRenderedCount = 0;
    renderChat();
  }

  function formatChapterTitle(title, chapterNum) {
    var t = title.trim();
    if (!t) return '第 ' + chapterNum + ' 章';
    var prefix = '第 ' + chapterNum + ' 章';
    // Already has Arabic numeral prefix — replace number, keep suffix
    var m = t.match(/^第\s*(\d+)\s*章[\s\u3000]*(.*)$/);
    if (m) { var suffix = m[2].trim(); return suffix ? prefix + ' ' + suffix : prefix; }
    // Chinese numeral prefix — replace with Arabic
    m = t.match(/^第[一二三四五六七八九十百千]+章[\s\u3000]*(.*)$/);
    if (m) { var suffix = m[1].trim(); return suffix ? prefix + ' ' + suffix : prefix; }
    // Bare number at start — wrap in prefix
    m = t.match(/^(\d+)[\s\u3000]*(.*)$/);
    if (m) { var suffix = m[2].trim(); return suffix ? prefix + ' ' + suffix : prefix; }
    return prefix + ' ' + t;
  }

  function saveCurrentContent() {
    if (!currentChapterId) return;
    var content = editor.value;
    currentChapter.content = content;
    api.put('/projects/' + projectId + '/chapters/' + currentChapterId, { content: content }).catch(function() {});
  }

  // 自动保存（debounce 800ms）
  editor.addEventListener('input', function() {
    if (saveTimer) clearTimeout(saveTimer);
    saveTimer = setTimeout(function() { saveCurrentContent(); }, 800);
  });

  // 手动保存按钮
  var saveBtn = body.querySelector('#saveBtn');
  var saveStatus = body.querySelector('#saveStatus');
  saveBtn.onclick = function() {
    saveCurrentContent();
    saveStatus.textContent = '✅ 已保存';
    clearTimeout(saveBtn._statusTimer);
    saveBtn._statusTimer = setTimeout(function() { saveStatus.textContent = ''; }, 2000);
  };

  // 刷新章节列表
  function refreshChapterList() {
    return api.get('/projects/' + projectId + '/chapters').then(async function(data) {
      chapters = data.chapters || [];
      chaptersContainer.innerHTML = chapters.map(function(c) {
        return '<div class="ch-item' + (c.id === currentChapterId ? ' active' : '') + '" data-id="' + c.id + '">' +
          '<span class="ch-title-text">' + escapeHtml(c.title) + '</span>' +
          '<input class="ch-title-input" type="text" value="' + escapeHtml(c.title) + '" />' +
          '<span class="ch-edit-icon">✎</span>' +
          '<span class="ch-delete-icon" title="删除章节">✕</span>' +
        '</div>';
      }).join('') + '<div class="new-ch-btn" id="newChapterBtn">➕ 新建章节</div>' +
        '<div class="new-ch-btn" id="autoCompleteBtn" style="border-color:#a855f7;color:#a855f7;">🚀 自动完本</div>' +
        '<span id="autoCompleteStatus" style="font-size:11px;color:#888;padding:2px 8px;display:none;"></span>';

      bindChapterEvents();
      var exists = chapters.some(function(c) { return c.id === currentChapterId; });
      if (!exists && chapters.length > 0) {
        currentChapterId = chapters[0].id;
        currentChapter = chapters[0];
        await loadChapterContent(currentChapterId);
      }
    }).catch(function(err) {
      console.error('刷新章节失败', err);
    });
  }

  function bindChapterEvents() {
    chaptersContainer.querySelectorAll('.ch-item').forEach(function(item) {
      var chId = item.dataset.id;

      item.addEventListener('click', async function(e) {
        if (e.target.classList.contains('ch-edit-icon') ||
            e.target.classList.contains('ch-title-input') ||
            e.target.classList.contains('ch-delete-icon')) return;
        saveCurrentContent();
        await loadChapterContent(chId);
      });

      // 编辑标题
      var editIcon = item.querySelector('.ch-edit-icon');
      var titleText = item.querySelector('.ch-title-text');
      var titleInput = item.querySelector('.ch-title-input');

      editIcon.addEventListener('click', function(e) {
        e.stopPropagation();
        titleText.style.display = 'none';
        titleInput.style.display = 'inline-block';
        titleInput.focus();
        titleInput.select();
      });

      titleInput.addEventListener('blur', function() {
        var newTitle = titleInput.value.trim() || '未命名章节';
        var chIdx = -1;
        for (var k = 0; k < chapters.length; k++) { if (chapters[k].id === chId) { chIdx = k; break; } }
        if (chIdx >= 0) newTitle = formatChapterTitle(newTitle, chIdx + 1);
        titleInput.value = newTitle;
        api.put('/projects/' + projectId + '/chapters/' + chId, { title: newTitle }).catch(function() {});
        titleText.textContent = newTitle;
        titleText.style.display = 'inline';
        titleInput.style.display = 'none';
        if (chId === currentChapterId) {
          chapterTitleDisplay.textContent = newTitle;
          chapterTitleInput.value = newTitle;
          var wd = WinMgr.find(win.id);
          if (wd) {
            wd.title = '✍️ ' + project.title + ' - ' + newTitle;
            wd.el.querySelector('.win-title').textContent = wd.title;
          }
        }
      });

      titleInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') this.blur();
      });

      // 删除
      var deleteIcon = item.querySelector('.ch-delete-icon');
      deleteIcon.addEventListener('click', function(e) {
        e.stopPropagation();
        if (!confirm('确定删除章节「' + titleText.textContent + '」吗？')) return;
        api.del('/projects/' + projectId + '/chapters/' + chId).then(function() {
          refreshChapterList();
        }).catch(function(err) {
          alert('删除失败: ' + err.message);
        });
      });
    });

    var newBtn = chaptersContainer.querySelector('#newChapterBtn');
    if (newBtn) {
      newBtn.onclick = function() {
        api.post('/projects/' + projectId + '/chapters', { title: '第 ' + (chapters.length + 1) + ' 章', content: '' }).then(function(data) {
          refreshChapterList();
          setTimeout(function() { loadChapterContent(data.id); }, 100);
        }).catch(function(err) {
          alert('删除失败: ' + err.message);
        });
      };
    }
    var acBtn = chaptersContainer.querySelector('#autoCompleteBtn');
    if (acBtn) { acBtn.onclick = startAutoComplete; }
  }

  bindChapterEvents();
  await loadChapterContent(currentChapterId);

  // === 顶部标题编辑 ===
  chapterTitleDisplay.addEventListener('click', function() {
    this.style.display = 'none';
    chapterTitleInput.style.display = 'inline-block';
    chapterTitleInput.focus();
    chapterTitleInput.select();
  });
  chapterTitleInput.addEventListener('blur', function() {
    var idx = chapters.indexOf(currentChapter);
    var newTitle = this.value.trim() || '未命名章节';
    if (idx >= 0) newTitle = formatChapterTitle(newTitle, idx + 1);
    this.value = newTitle;
    api.put('/projects/' + projectId + '/chapters/' + currentChapterId, { title: newTitle }).catch(function() {});
    chapterTitleDisplay.textContent = newTitle;
    chapterTitleDisplay.style.display = 'inline';
    this.style.display = 'none';
    refreshChapterList();
  });
  chapterTitleInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') this.blur();
  });

  var _lastSetTitle = null;  // set by set_chapter_title tool during streaming
  var _skipAutoFill = false;

  // === AI 聊天 ===
  function sendToAI(userMessage) {
    return new Promise(function(resolve) {
      if (sendingInProgress) { resolve(); return; }
      sendingInProgress = true;
      sendBtn.disabled = true;
      sendBtn.textContent = '等待中...';

      currentChatHistory.push({ role: 'user', content: userMessage });
      saveChatHistory(projectId, currentChapterId, currentChatHistory).then(function() {}).catch(function(){});
      renderChat();

      var customSys = window.getSetting('systemPrompt');
      var idx = chapters.indexOf(currentChapter);
      var prevChs = chapters.slice(Math.max(0, idx - 3), idx);
      var prevText = prevChs.length
        ? prevChs.map(function(ch, i) { return '第' + (Math.max(0, idx - 3) + i + 1) + '章 ' + ch.title + '：\n' + (ch.content || '(空)'); }).join('\n\n')
        : '（无前文章节）';
      var sysContent = (customSys ? customSys + '\n\n---\n\n' : '') +
        '书名：' + project.title + '\n作者：' + (project.author || '匿名') + '\n\n' +
        '当前章节：第 ' + (idx + 1) + ' 章「' + currentChapter.title + '」\n\n' +
        '大纲：' + (project.outline || '无') + '\n\n' +
        '设定：' + (project.setting || '无') + '\n\n' +
        '前文摘要：\n' + prevText + '\n\n---\n\n' +
        '请根据以上上下文续写当前章节。当前章节已有内容：\n' + (currentChapter.content || '（空）');
      var msgs = [{ role: 'system', content: sysContent }].concat(
        buildChatMessages(currentChatHistory.slice(-10))
      );

      var thinkingFullText = '';
      var aiFullText = '';

      streamChat(msgs,
        function(chunk) {
          thinkingFullText += chunk;
          var last = currentChatHistory[currentChatHistory.length - 1];
          if (last && last.role === 'thinking') {
            last.content = thinkingFullText;
          } else {
            currentChatHistory.push({ role: 'thinking', content: thinkingFullText });
          }
          debouncedSaveHistory();
          renderChat();
        },
        function(chunk) {
          aiFullText += chunk;
          var last = currentChatHistory[currentChatHistory.length - 1];
          if (last && last.role === 'ai') {
            last.content = aiFullText;
          } else {
            currentChatHistory.push({ role: 'ai', content: aiFullText });
          }
          debouncedSaveHistory();
          renderChat();
        },
        function(errMsg) {
          currentChatHistory.push({ role: 'ai', content: '⚠️ ' + errMsg });
          debouncedSaveHistory();
          renderChat();
        },
        function() {
          sendingInProgress = false;
          sendBtn.disabled = false;
          sendBtn.textContent = '发送';
          saveChatHistory(projectId, currentChapterId, currentChatHistory).catch(function(){}).then(function() { resolve(); });
          if (window.appSettings && window.appSettings.auto_fill && !_skipAutoFill) {
            autoFillFromAI();
          }
          _skipAutoFill = false;
        },
        function(txt) {
          sendBtn.textContent = txt;
        },
        projectId,
        function(e) {
          if (e.type === 'tool_result' && e.data.name === 'set_chapter_title') {
            _lastSetTitle = e.data.result;
            var m = e.data.result.match(/set to:\s*(.+)$/);
            if (m) {
              var newTitle = m[1].trim();
              var tidx = chapters.indexOf(currentChapter);
              if (tidx >= 0) newTitle = formatChapterTitle(newTitle, tidx + 1);
              chapterTitleDisplay.textContent = newTitle;
              chapterTitleInput.value = newTitle;
              var wd = WinMgr.find(win.id);
              if (wd) {
                wd.title = '✍️ ' + project.title + ' - ' + newTitle;
                wd.el.querySelector('.win-title').textContent = wd.title;
              }
              // Update sidebar and local state
              currentChapter.title = newTitle;
              refreshChapterList();
            }
          }
          if (e.type === 'tool_status') {
            currentChatHistory.push({
              role: 'tool_call',
              name: e.data.name,
              arguments: e.data.arguments,
              tool_call_id: e.data.tool_call_id,
              status: 'pending',
              result: null,
            });
            debouncedSaveHistory();
            renderChat();
          } else if (e.type === 'tool_result') {
            for (var i = currentChatHistory.length - 1; i >= 0; i--) {
              var m = currentChatHistory[i];
              if (m.role === 'tool_call' && m.name === e.data.name && m.status === 'pending') {
                m.status = 'done';
                m.result = e.data.result;
                if (e.data.tool_call_id) m.tool_call_id = e.data.tool_call_id;
                debouncedSaveHistory();
                renderChat();
                break;
              }
            }
          }
        },
        currentChapterId
      );
    });
  }

  sendBtn.onclick = function() {
    var msg = chatInput.value.trim();
    if (!msg) return;
    chatInput.value = '';
    sendToAI(msg);
  };

  chatInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') sendBtn.click();
  });

  function autoFillFromAI() {
    var lastAi = null;
    for (var i = currentChatHistory.length - 1; i >= 0; i--) {
      if (currentChatHistory[i].role === 'ai') { lastAi = currentChatHistory[i]; break; }
    }
    if (!lastAi) return;
    var text = lastAi.content.trim();

    // 尝试提取标题
    var toolTitle = _lastSetTitle;
    if (toolTitle) {
      var m = toolTitle.match(/set to:\s*(.+)$/);
      if (m) {
        var newTitle = m[1].trim();
        chapterTitleDisplay.textContent = newTitle;
        chapterTitleInput.value = newTitle;
        chapterTitleInput.dispatchEvent(new Event('blur'));
      }
    } else {
      var titleMatch = text.match(/^#\s+(.+?)(?:\n|$)/);
      if (titleMatch) {
        var newTitle = titleMatch[1].trim();
        chapterTitleDisplay.textContent = newTitle;
        chapterTitleInput.value = newTitle;
        chapterTitleInput.dispatchEvent(new Event('blur'));
        text = text.substring(titleMatch[0].length).trim();
      }
    }
    // 填入编辑器
    editor.value += (editor.value ? '\n\n' : '') + text;
    saveCurrentContent();
    _lastSetTitle = null;
  }

  // 填入
  fillBtn.onclick = autoFillFromAI;

  // 清空对话
  clearChatBtn.onclick = async function() {
    if (!confirm('清空本章对话记录？')) return;
    currentChatHistory = [];
    chatRenderedCount = 0;
    chatHistory.innerHTML = '';
    await saveChatHistory(projectId, currentChapterId, currentChatHistory);
  };

  // 记忆管理
  memoriesBtn.onclick = function() { openMemoryEditor(projectId); };

  // 准备新章节（一次请求：记忆管理 + 正文写作）
  prepareBtn.onclick = async function() {
    if (sendingInProgress) return;
    var idx = chapters.indexOf(currentChapter);
    var prevChapters = chapters.slice(Math.max(0, idx - 3), idx);
    var currentNum = idx + 1;

    var prevContent = prevChapters.length > 0
      ? prevChapters.map(function(ch, i) {
          return '第' + (Math.max(0, idx - 3) + i + 1) + '章 ' + ch.title + '：\n' + (ch.content || '(空)');
        }).join('\n\n')
      : '（无前文章节）';

    var message =
      '书名：' + project.title + '\n作者：' + (project.author || '匿名') + '\n\n' +
      '（当前准备续写第 ' + currentNum + ' 章：' + currentChapter.title + '）\n\n' +
      '大纲：' + (project.outline || '无') + '\n设定：' + (project.setting || '无') + '\n\n' +
      '前 ' + prevChapters.length + ' 章内容：\n' + prevContent + '\n\n' +
      '请按系统提示词的工作流程完成本章创作：先管理记忆（读取/清理/存储），再设置标题，最后输出正文。';

    chatInput.value = '';
    _skipAutoFill = true;
    await sendToAI(message);
  };

  renderChat();
}

// ===== 记忆编辑器 =====
function openMemoryEditor(projectId) {
  var winId = 'mem_editor_' + projectId;
  var existing = WinMgr.find(winId);
  if (existing) { WinMgr.focus(winId); return; }

  var win = WinMgr.create('📖 记忆管理', '<div style="text-align:center;padding:20px;color:#666;">⏳ 加载中...</div>', 600, 450, winId);

  function render() {
    api.get('/memory/' + projectId).then(function(data) {
      var mems = (data && data.memories) || [];
      var html = '<div style="margin-bottom:8px;display:flex;gap:4px;">' +
        '<input id="memNewKey" placeholder="key (英文)" style="flex:2;padding:4px;" />' +
        '<input id="memNewContent" placeholder="[ChX] content" style="flex:4;padding:4px;" />' +
        '<input id="memNewTags" placeholder="tags" style="flex:1;padding:4px;" />' +
        '<button id="memAddBtn" class="btn btn-primary" style="padding:4px 8px;">➕</button></div>';
      if (mems.length === 0) {
        html += '<div style="color:#888;padding:10px;">暂无记忆</div>';
      } else {
        html += mems.map(function(m) {
          return '<div style="border-bottom:1px solid #333;padding:6px 0;">' +
            '<div style="display:flex;gap:4px;margin-bottom:2px;">' +
            '<input class="mem-key" value="' + escapeHtml(m.key) + '" data-id="' + m.id + '" style="flex:2;padding:2px;" />' +
            '<input class="mem-content" value="' + escapeHtml(m.content) + '" data-id="' + m.id + '" style="flex:4;padding:2px;" />' +
            '<input class="mem-tags" value="' + escapeHtml((m.tags||[]).join(',')) + '" data-id="' + m.id + '" style="flex:1;padding:2px;" />' +
            '<button class="mem-save-btn" data-id="' + m.id + '" style="padding:2px 6px;">💾</button>' +
            '<button class="mem-del-btn" data-id="' + m.id + '" style="padding:2px 6px;">✕</button></div>' +
            '<div style="color:#666;font-size:11px;">' + (m.created_at || '') + '</div></div>';
        }).join('');
      }
      win.el.querySelector('.win-body').innerHTML = html;

      // Add new memory
      win.el.querySelector('#memAddBtn').onclick = function() {
        var key = win.el.querySelector('#memNewKey').value.trim();
        var content = win.el.querySelector('#memNewContent').value.trim();
        var tagsStr = win.el.querySelector('#memNewTags').value.trim();
        if (!key || !content) return;
        var tags = tagsStr ? tagsStr.split(',').map(function(t) { return t.trim(); }).filter(Boolean) : [];
        api.post('/memory/' + projectId, { key: key, content: content, tags: tags }).then(function() { render(); }).catch(function(e) { alert('Error: ' + e.message); });
      };

      // Save existing
      Array.from(win.el.querySelectorAll('.mem-save-btn')).forEach(function(btn) {
        btn.onclick = function() {
          var id = btn.getAttribute('data-id');
          var row = btn.parentElement;
          var key = row.querySelector('.mem-key').value.trim();
          var content = row.querySelector('.mem-content').value.trim();
          var tagsStr = row.querySelector('.mem-tags').value.trim();
          var tags = tagsStr ? tagsStr.split(',').map(function(t) { return t.trim(); }).filter(Boolean) : [];
          api.put('/memory/' + projectId + '/' + id, { key: key, content: content, tags: tags }).then(function() { render(); }).catch(function(e) { alert('Error: ' + e.message); });
        };
      });

      // Delete
      Array.from(win.el.querySelectorAll('.mem-del-btn')).forEach(function(btn) {
        btn.onclick = function() {
          var id = btn.getAttribute('data-id');
          if (!confirm('Delete this memory?')) return;
          api.delete('/memory/' + projectId + '/' + id).then(function() { render(); }).catch(function(e) { alert('Error: ' + e.message); });
        };
      });
    }).catch(function(e) {
      win.el.querySelector('.win-body').innerHTML = '<div class="text-error">加载失败: ' + escapeHtml(e.message) + '</div>';
    });
  }

  render();
}


// ===== 4. 系统设置 =====
function openSettings() {
  var existing = WinMgr.find('settings_win');
  if (existing) {
    WinMgr.focus('settings_win');
    return;
  }
  var loadBtn =
    '<div style="text-align:center;padding:20px 0;color:#888;">⏳ 加载设置中...</div>';
  var win = WinMgr.create('⚙️ 系统设置', loadBtn, 520, 480, 'settings_win');
  var body = win.el.querySelector('.win-body');

  api.get('/settings?_t=' + Date.now()).then(function(data) {
    data = data || {};
    body.innerHTML =
      '<div style="color:#aaa;margin-bottom:8px;">⚙️ 配置面板（保存到服务器）</div>' +
      '<div><label style="color:#888;">API 端点</label><br>' +
        '<input type="text" id="setting_api_endpoint" value="' + escapeHtml(data.api_endpoint || 'https://opencode.ai/zen/v1') + '" style="width:100%;" /></div>' +
      '<div><label style="color:#888;">API 密钥</label><br>' +
        '<input type="text" id="setting_api_key" value="' + escapeHtml(data.api_key || '') + '" style="width:100%;" /></div>' +
      '<div><label style="color:#888;">默认模型</label><br>' +
        '<input type="text" id="setting_model" value="' + escapeHtml(data.model || 'deepseek-v4-flash-free') + '" style="width:100%;" /></div>' +
      '<div><label style="color:#888;margin-top:8px;display:block;">系统提示词（每次对话自动前置）</label>' +
        '<textarea id="setting_system_prompt" style="width:100%;height:80px;resize:vertical;">' + escapeHtml(data.system_prompt || '') + '</textarea></div>' +
      '<div style="margin-top:8px;"><label style="color:#888;">' +
        '<input type="checkbox" id="setting_auto_fill"' + (data.auto_fill ? ' checked' : '') + ' /> ' +
        '自动填入：AI 完成后自动提取标题和内容填入编辑区</label></div>' +
      '<div style="margin-top:8px;">' +
        '<button class="btn btn-primary" id="saveSettingsBtn">💾 保存</button>' +
        '<button class="btn" id="testConnBtn" style="margin-left:6px;">🔌 测试连接</button>' +
        '<span id="settingFeedback" style="color:#0f0;margin-left:8px;"></span>' +
      '</div>' +
      '<div style="margin-top:8px" id="modelList"></div>';

    var defaultPrompt = data.system_prompt || '';
    body.querySelector('#saveSettingsBtn').onclick = function() {
      var sysPrompt = body.querySelector('#setting_system_prompt').value.trim();
      if (!sysPrompt) {
        sysPrompt = defaultPrompt;
        body.querySelector('#setting_system_prompt').value = defaultPrompt;
      }
      var s = {
        api_endpoint: body.querySelector('#setting_api_endpoint').value.trim() || 'https://opencode.ai/zen/v1',
        api_key: body.querySelector('#setting_api_key').value.trim(),
        model: body.querySelector('#setting_model').value.trim() || 'deepseek-v4-flash-free',
        system_prompt: sysPrompt,
        auto_fill: body.querySelector('#setting_auto_fill').checked,
      };
      api.put('/settings', s).then(function() {
        window.appSettings = s;
        localStorage.setItem('app_settings', JSON.stringify({
          apiEndpoint: s.api_endpoint,
          apiKey: s.api_key,
          model: s.model,
          systemPrompt: s.system_prompt,
          autoFill: s.auto_fill,
        }));
        body.querySelector('#settingFeedback').textContent = '✅ 已保存';
        setTimeout(function() { body.querySelector('#settingFeedback').textContent = ''; }, 2000);
      }).catch(function(err) {
        body.querySelector('#settingFeedback').textContent = '❌ ' + err.message;
      });
    };

    body.querySelector('#testConnBtn').onclick = function() {
      var fb = body.querySelector('#settingFeedback');
      fb.textContent = '⏳ 测试中...';
      var endpoint = body.querySelector('#setting_api_endpoint').value.trim() || 'https://opencode.ai/zen/v1';
      var saved = localStorage.getItem('ai_base_url');
      localStorage.setItem('ai_base_url', endpoint);
      api.get('/models').then(function(data) {
        var models = data.models || [];
        fb.textContent = '✅ 连接成功 (' + models.length + ' 个模型)';
        var ml = body.querySelector('#modelList');
        ml.innerHTML = '<div style="color:#888;margin-bottom:4px;">可用模型：</div>' +
          models.map(function(m) { return '<span style="display:inline-block;border:1px solid #555;padding:1px 6px;margin:2px;font-size:11px;color:#888;">' + escapeHtml(m.id) + '</span>'; }).join('');
      }).catch(function(err) {
        fb.textContent = '❌ 连接失败: ' + err.message;
      }).finally(function() {
        if (saved) localStorage.setItem('ai_base_url', saved);
      });
    };
  }).catch(function(err) {
    body.innerHTML = '<div class="text-error">加载设置失败: ' + escapeHtml(err.message) + '</div>';
  });
}

// ===== 5. 操作日志（实时 + 网络请求 + 详细动作） =====
function openLogs() {
  var html =
    '<div style="margin-bottom:6px;display:flex;justify-content:space-between;align-items:center;">' +
      '<span style="color:#888;">🔴 实时日志（最新在前）</span>' +
      '<button class="btn" id="clearLogsBtn" style="font-size:11px;padding:1px 8px;">清空</button>' +
    '</div>' +
    '<div id="logsContent" style="font-size:11px;max-height:320px;overflow-y:auto;background:#050505;border:1px solid #222;padding:4px;">' +
      renderLogEntries(window.__uiLogs || []) +
    '</div>';
  var win = WinMgr.create('📜 操作日志', html, 640, 400, 'logs_win');

  win.el.querySelector('#clearLogsBtn').onclick = function() {
    window.__uiLogs = [];
    var el = win.el.querySelector('#logsContent');
    if (el) el.innerHTML = '<div style="color:#555;padding:10px;text-align:center;">已清空</div>';
  };

  // 定时刷新
  var interval = setInterval(function() {
    var el = win.el.querySelector('#logsContent');
    if (el && document.body.contains(el)) {
      el.innerHTML = renderLogEntries(window.__uiLogs || []);
    } else {
      clearInterval(interval);
    }
  }, 1000);
}

function renderLogEntries(logs) {
  if (!logs || logs.length === 0) return '<div style="color:#555;padding:10px;text-align:center;">暂无日志</div>';
  return logs.map(function(e) {
    var c = e.type === 'error' ? '#f55' : (e.type === 'warn' ? '#ffb86b' : (e.type === 'verbose' ? '#555' : '#888'));
    var level = e.type === 'error' ? 'ERR' : (e.type === 'warn' ? 'WRN' : (e.type === 'verbose' ? 'DBG' : 'INF'));
    return '<div style="border-bottom:1px solid #1a1a1a;padding:3px 4px;display:flex;gap:6px;word-break:break-all;">' +
      '<span style="color:#555;flex-shrink:0;width:50px;">[' + e.time + ']</span>' +
      '<span style="color:' + c + ';flex-shrink:0;width:26px;">[' + level + ']</span>' +
      '<span style="color:' + c + ';">' + escapeHtml(e.text) + '</span>' +
      '</div>';
  }).join('');
}

// ===== 6. 对话（独立 AI 聊天，无项目上下文） =====
async function openChat() {
  var winId = 'chat_win';
  var existing = WinMgr.find(winId);
  if (existing) { WinMgr.focus(winId); return; }

  var html =
    '<div class="writer-layout" style="height:100%;">' +
      '<div class="writer-right" style="width:100%;border-left:none;height:100%;display:flex;flex-direction:column;">' +
        '<div class="chat-history" id="chatHistoryFree" style="flex:1;overflow-y:auto;border-bottom:1px solid #222;padding-bottom:4px;margin-bottom:4px;min-height:80px;"></div>' +
        '<div class="chat-input-area">' +
          '<input type="text" id="chatInputFree" placeholder="输入消息..." />' +
          '<button id="sendBtnFree">发送</button>' +
          '<button id="clearChatBtn" style="border-color:#f55;color:#f55;">清空</button>' +
        '</div>' +
      '</div>' +
    '</div>';

  var win = WinMgr.create('💬 AI 对话', html, 500, 450, winId);
  var body = win.el.querySelector('.win-body');
  var chatHistory = body.querySelector('#chatHistoryFree');
  var chatInput = body.querySelector('#chatInputFree');
  var sendBtn = body.querySelector('#sendBtnFree');
  var clearBtn = body.querySelector('#clearChatBtn');

  var chatKey = 'free';
  var sendingInProgress = false;
  var chatSaveTimer = null;
  var chatMessages = [];

  async function loadChat(key) {
    try {
      var data = await api.get('/chat/' + key);
      return data.messages || [];
    } catch(e) { return []; }
  }
  async function saveChat(key, msgs) {
    try { await api.put('/chat/' + key, { messages: msgs }); } catch(e) {}
  }
  function debouncedSaveChat() {
    if (chatSaveTimer) clearTimeout(chatSaveTimer);
    chatSaveTimer = setTimeout(function() {
      api.put('/chat/' + chatKey, { messages: chatMessages }).catch(function(){});
    }, 1500);
  }

  chatMessages = await loadChat(chatKey);
  var chatRenderedCount = 0;

  function renderChat() {
    while (chatRenderedCount < chatMessages.length) {
      var msg = chatMessages[chatRenderedCount];
      if (!msg) { chatRenderedCount++; continue; }
      var div = document.createElement('div');
      if (msg.role === 'tool_call') {
        div.className = 'chat-msg tool-call';
        var argsHtml = '<span style="color:#58a6ff;">' + escapeHtml(msg.arguments) + '</span>';
        var resultHtml = msg.status === 'done' && msg.result
          ? '<br><span style="color:#3fb950;">→ ' + escapeHtml(msg.result) + '</span>'
          : ' <span style="color:#888;">⏳</span>';
        div.innerHTML = '<span style="color:#888;">🛠️ ' + escapeHtml(msg.name) + '</span> ' + argsHtml + resultHtml;
      } else {
        div.className = 'chat-msg ' + (msg.role === 'thinking' ? 'thinking' : msg.role);
        if (msg.role === 'thinking') {
          div.textContent = '🤔 ' + msg.content;
        } else if (msg.role === 'user') {
          div.textContent = '👤 ' + msg.content;
        } else {
          div.textContent = '🤖 ' + msg.content;
        }
      }
      chatHistory.appendChild(div);
      chatRenderedCount++;
    }
    if (chatRenderedCount > 0) {
      var lastMsg = chatMessages[chatRenderedCount - 1];
      var lastEl = chatHistory.lastElementChild;
      if (lastEl && lastMsg) {
        if (lastMsg.role === 'tool_call') {
          var argsHtml = '<span style="color:#58a6ff;">' + escapeHtml(lastMsg.arguments) + '</span>';
          var resultHtml = lastMsg.status === 'done' && lastMsg.result
            ? '<br><span style="color:#3fb950;">→ ' + escapeHtml(lastMsg.result) + '</span>'
            : ' <span style="color:#888;">⏳</span>';
          lastEl.innerHTML = '<span style="color:#888;">🛠️ ' + escapeHtml(lastMsg.name) + '</span> ' + argsHtml + resultHtml;
        } else if (lastMsg.role !== 'user') {
          lastEl.textContent = (lastMsg.role === 'thinking' ? '🤔 ' : '🤖 ') + lastMsg.content;
        }
      }
    }
    chatHistory.scrollTop = chatHistory.scrollHeight;
  }

  async function sendMessage(userMessage) {
    if (sendingInProgress) return;
    sendingInProgress = true;
    sendBtn.disabled = true;
    sendBtn.textContent = '等待中...';

    chatMessages.push({ role: 'user', content: userMessage });
    await saveChat(chatKey, chatMessages);
    renderChat();

    var customSys = window.getSetting('systemPrompt');
    var msgs = customSys
      ? [{ role: 'system', content: customSys }].concat(buildChatMessages(chatMessages.slice(-20)))
      : buildChatMessages(chatMessages.slice(-20));

    var thinkingFullText = '';
    var aiFullText = '';

    await streamChat(msgs,
      function(chunk) {
        thinkingFullText += chunk;
        var last = chatMessages[chatMessages.length - 1];
        if (last && last.role === 'thinking') {
          last.content = thinkingFullText;
        } else {
          chatMessages.push({ role: 'thinking', content: thinkingFullText });
        }
        debouncedSaveChat();
        renderChat();
      },
      function(chunk) {
        aiFullText += chunk;
        var last = chatMessages[chatMessages.length - 1];
        if (last && last.role === 'ai') {
          last.content = aiFullText;
        } else {
          chatMessages.push({ role: 'ai', content: aiFullText });
        }
        debouncedSaveChat();
        renderChat();
      },
      function(errMsg) {
        chatMessages.push({ role: 'ai', content: '⚠️ ' + errMsg });
        debouncedSaveChat();
        renderChat();
      },
      function() {
        sendingInProgress = false;
        sendBtn.disabled = false;
        sendBtn.textContent = '发送';
        saveChat(chatKey, chatMessages).catch(function(){});
      },
      function(txt) {
        sendBtn.textContent = txt;
      },
      null,
      function(e) {
        if (e.type === 'tool_status') {
          chatMessages.push({ role: 'tool_call', name: e.data.name, arguments: e.data.arguments, status: 'pending', result: null });
          debouncedSaveChat();
          renderChat();
        } else if (e.type === 'tool_result') {
          for (var i = chatMessages.length - 1; i >= 0; i--) {
            var m = chatMessages[i];
            if (m.role === 'tool_call' && m.name === e.data.name && m.status === 'pending') {
              m.status = 'done';
              m.result = e.data.result;
              debouncedSaveChat();
              renderChat();
              break;
            }
          }
        }
      }
    );
  }

  sendBtn.onclick = function() {
    var msg = chatInput.value.trim();
    if (!msg) return;
    chatInput.value = '';
    sendMessage(msg);
  };

  chatInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') sendBtn.click();
  });

  clearBtn.onclick = async function() {
    chatMessages = [];
    chatRenderedCount = 0;
    chatHistory.innerHTML = '';
    await saveChat(chatKey, chatMessages);
  };

  renderChat();
}

// ===== 7. 帮助 =====
function openHelp() {
  WinMgr.create('❓ 帮助',
    '<div style="color:#aaa;">📖 使用指南</div>' +
    '<div style="color:#aaa;margin-top:8px;">点击「开始创作」管理您的项目。</div>' +
    '<div style="color:#aaa;">在写作工作区，您可以编辑章节、与AI对话辅助写作。</div>' +
    '<div style="color:#aaa;">章节标题旁的 ✎ 可编辑章节名称；✕ 可删除章节。</div>' +
    '<div style="color:#aaa;">「准备新章节」基于大纲+设定+前文自动生成提示词发给AI。</div>',
    500, 320, 'help_win');
}
