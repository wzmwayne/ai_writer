// ============================================================
// 全局错误捕获 + 操作日志
// ============================================================
window.__uiLogs = [];
window.appSettings = null;

window.uiLog = function(type, text) {
  var entry = { type: type, text: text, time: new Date().toLocaleTimeString() };
  window.__uiLogs.unshift(entry);
  if (window.__uiLogs.length > 200) window.__uiLogs.length = 200;
  if (type === 'error') console.error('[UI:' + type + ']', text);
  else console.log('[UI:' + type + ']', text);

  var container = document.getElementById('logFeed');
  if (container) {
    container.innerHTML = window.__uiLogs.filter(function(e) { return e.type !== 'verbose'; }).slice(0, 8).map(function(e) {
      var c = e.type === 'error' ? '#f55' : (e.type === 'warn' ? '#ffb86b' : '#888');
      return '<div style="font-size:11px;color:' + c + ';border-bottom:1px solid #1a1a1a;padding:2px 0;">[' + e.time + '] ' + window.escapeHtml(e.text) + '</div>';
    }).join('');
    if (!window.__uiLogs.filter(function(e) { return e.type !== 'verbose'; }).length) container.innerHTML = '<div style="font-size:11px;color:#555;">暂无操作记录</div>';
  }

  if (type === 'error' && window.openLogs) {
    var existing = window.WinMgr && window.WinMgr.find('logs_win');
    if (!existing) window.openLogs();
  }
};

window.onerror = function(msg, url, line, col, err) {
  window.uiLog('error', msg + ' (' + (url || '').split('/').pop() + ':' + line + ')');
};

window.getSetting = function(key) {
  // Tier 1: window.appSettings (from backend), check both camelCase and snake_case
  if (window.appSettings) {
    var val = window.appSettings[key];
    if (val === undefined) {
      // Convert camelCase to snake_case: systemPrompt → system_prompt
      var snake = key.replace(/[A-Z]/g, function(m) { return '_' + m.toLowerCase(); });
      val = window.appSettings[snake];
    }
    if (val !== undefined && val !== '') return val;
  }
  // Tier 2: localStorage (camelCase keys, set on settings save)
  var ls = JSON.parse(localStorage.getItem('app_settings') || '{}');
  if (ls[key] !== undefined && ls[key] !== '') return ls[key];
  // Tier 3: minimal fallback (model only, system prompt loads from backend)
  var modelDefault = 'deepseek-v4-flash-free';
  if (key === 'model' || key === 'model') return modelDefault;
  return '';
};

// ============================================================
// 桌面初始化 — 侧栏导航 / 任务栏时钟 / 概览刷新
// ============================================================
function refreshOverviewStats() {
  var elP = document.querySelector('#statProjects span');
  var elC = document.querySelector('#statChapters span');
  var elR = document.querySelector('#statRecent span');
  if (!elP) return;

  api.get('/projects').then(function(data) {
    var projects = data.projects || [];
    var totalCh = 0;
    projects.forEach(function(p) { totalCh += (p.chapter_count || 0); });
    elP.textContent = projects.length;
    elC.textContent = totalCh;
    window.uiLog('info', '概览 — ' + projects.length + ' 个项目, ' + totalCh + ' 章');

    var sorted = projects.slice().sort(function(a, b) {
      return new Date(b.updated_at || 0) - new Date(a.updated_at || 0);
    });
    elR.textContent = sorted.length > 0 && sorted[0].updated_at
      ? (window.fmtDate || function(d){return d})(sorted[0].updated_at) + ' — ' + sorted[0].title
      : '暂无活动';
  }).catch(function(err) {
    elP.textContent = '加载失败';
    elC.textContent = '加载失败';
    window.uiLog('error', '概览加载失败: ' + err.message);
  });
}

function setupSidebar() {
  var icons = document.querySelectorAll('.icon-item');
  icons.forEach(function(el) {
    el.onclick = function() {
      icons.forEach(function(i) { i.classList.remove('active'); });
      this.classList.add('active');
      var titleMap = {
        overview: '系统概览', chat: 'AI 对话', startwriting: '项目与写作',
        settings: '系统设置', logs: '操作日志', help: '帮助',
      };
      var pt = document.getElementById('previewTitle');
      if (pt) pt.textContent = titleMap[this.dataset.app] || '系统概览';

      switch (this.dataset.app) {
        case 'overview': openOverview(); refreshOverviewStats(); break;
        case 'chat': openChat(); refreshOverviewStats(); break;
        case 'startwriting': openProjectList(); break;
        case 'settings': openSettings(); break;
        case 'logs': openLogs(); break;
        case 'help': openHelp(); break;
      }
    };
  });
}

// 脚本已在 </body> 前加载，DOM 就绪，无需等待 DOMContentLoaded
setupSidebar();

var clockEl = document.getElementById('clock');
if (clockEl) {
  function tick() { clockEl.textContent = new Date().toLocaleTimeString(); }
  tick();
  setInterval(tick, 1000);
}

refreshOverviewStats();

var defaultIcon = document.querySelector('.icon-item[data-app="overview"]');
if (defaultIcon) defaultIcon.click();

window.uiLog('info', '桌面就绪');

// 后台加载设置，不阻塞初始化
api.get('/settings').then(function(data) {
  window.appSettings = data;
}).catch(function() {
  window.appSettings = null;
});
