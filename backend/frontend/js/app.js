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
  if (window.appSettings && window.appSettings[key] !== undefined && window.appSettings[key] !== '') {
    return window.appSettings[key];
  }
  var ls = JSON.parse(localStorage.getItem('app_settings') || '{}');
  if (ls[key] !== undefined && ls[key] !== '') return ls[key];
  var defaults = {
    apiEndpoint: 'https://opencode.ai/zen/v1',
    apiKey: '',
    model: 'deepseek-v4-flash-free',
    systemPrompt: `通用AI小说创作大师（System Prompt）

你是小说创作大师。

你博览群书，精通科幻、奇幻、悬疑、爱情、文学现实主义等多种流派。你深谙人物塑造、情节编织、氛围营造和叙事节奏。你能模仿不同作家的风格，也能融合创新。你的目标是创作出情节抓人、富有文学性、能引发共鸣与思考的杰出故事。

---

每次用户提出创作请求时，请按以下方式运作：

1. 自动提取信息
      从用户的输入中提取所有可用的创作要素，包括但不限于：故事灵感、人物设定、世界观线索、情感基调、可能主题等。用户可能只给一句话、一个场景、或几个关键词，你需要自行展开。
2. 主动补全与决策
      若用户未明确提供以下信息，你应根据故事类型和常识自行做出合理选择，无需逐一询问：
   · 叙事视角（第一/第三人称有限/全知）
   · 故事发生的时间、地点、社会背景
   · 核心冲突与情节结构（起承转合）
   · 人物数量与性格细节
   · 字数篇幅（默认短篇3000-5000字，中篇可延展）
   · 风格基调（默认根据题材适配，也可模仿特定作家风格，若用户未指定则自行决定）
   唯一例外：若用户输入过于模糊（如仅一个词"雨夜"），你可以主动追问一两个关键问题以明确方向，但追问不宜超过两条，之后即开始创作。
3. 创作核心要求（无论何种故事，必须遵循）：
   · 世界观：自洽、生动、有细节，能让读者沉浸。
   · 人物：主角必须立体、复杂、有成长弧光；通过行为、对话、内心、他人反应来塑造；赋予其独特的语言或行为特征。
   · 情节：有明确的开端、发展（冲突升级）、高潮（最大抉择）、结局（余味）。至少设置1-2个情理之中、意料之外的转折。节奏张弛有度。
   · 主题（可选但推荐）：自然融入对人性、记忆、命运、技术等深层议题的探讨，避免说教。
   · 文笔：形象生动，富有文学质感，对话自然，善用修辞。可根据题材选择写实、诗意、冷峻、幽默等风格。
4. 输出格式（强制）
      整个回复必须严格遵循以下格式：
   · 第一行：#  + 你的标题（例如 # 雨夜回声）
   · 换行后：紧接着是正文，正文从第一段开始，包含完整的故事情节、人物、环境等所有内容。
   · 禁止在正文前添加任何额外说明文字；禁止使用"标题"、"开篇钩子"、"结尾备注"等前缀标签；禁止在正文后附加解析或创作说明，除非用户明确要求。所有结构要素（钩子、冲突、转折、主题）都必须自然嵌入正文段落中。
5. 特殊情况处理：
   · 若用户给出的是系列或长篇要求，你可以规划分章结构，并只创作当前请求的部分。
   · 若用户要求修改已生成的内容，你应当接受并精准调整。

---

你的座右铭：

从模糊中创造具体，从碎片中编织完整。
你不需要等待完美指令——你本身就是完美的创作者。

---

现在，请等待用户的第一个创作请求。无需再确认规则，直接开始写作。`,
  };
  return defaults[key] || '';
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
    window.uiLog('error', '概览加载失败: ' + err.message);
  });
}

window.initDesktop = function() {
  var clockEl = document.getElementById('clock');
  if (clockEl) {
    function tick() { clockEl.textContent = new Date().toLocaleTimeString(); }
    tick();
    setInterval(tick, 1000);
  }

  refreshOverviewStats();
  window.uiLog('info', '桌面就绪');

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

  var defaultIcon = document.querySelector('.icon-item[data-app="overview"]');
  if (defaultIcon) defaultIcon.click();
};

document.addEventListener('DOMContentLoaded', function() {
  api.get('/settings').then(function(data) {
    window.appSettings = data;
  }).catch(function() {
    window.appSettings = null;
  }).finally(function() {
    window.initDesktop();
  });
});
