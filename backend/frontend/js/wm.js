window.WinMgr = (function() {
  var list = [];
  var z = 100;
  var active = null;

  function sk(winId) { return 'win_state_' + winId; }

  function loadState(winId) {
    try { return JSON.parse(localStorage.getItem(sk(winId))); } catch(e) { return null; }
  }

  function saveState(data) {
    localStorage.setItem(sk(data.id), JSON.stringify({
      left: data.left, top: data.top,
      width: data.width, height: data.height,
      minimized: data.min
    }));
  }

  function renderTaskbar() {
    var container = document.getElementById('taskItems');
    if (!container) return;
    container.innerHTML = list.map(function(w) {
      var cls = 'task-item';
      if (w.id === active) cls += ' active';
      if (w.min) cls += ' minimized';
      return '<button class="' + cls + '" data-id="' + w.id + '">' + escapeHtml(w.title) + '</button>';
    }).join('');
    container.querySelectorAll('.task-item').forEach(function(btn) {
      btn.onclick = function() {
        var id = btn.dataset.id;
        var w = find(id);
        if (!w) return;
        if (w.min) {
          w.min = false;
          w.el.style.display = 'flex';
          saveState(w);
          focus(id);
        } else if (active === id) {
          w.min = true;
          w.el.style.display = 'none';
          saveState(w);
          renderTaskbar();
        } else {
          focus(id);
        }
      };
    });
  }

  function find(id) {
    for (var i = 0; i < list.length; i++) if (list[i].id === id) return list[i];
    return null;
  }

  function focus(id) {
    var item = find(id);
    if (!item || item.min) return;
    item.z = ++z;
    item.el.style.zIndex = item.z;
    list.forEach(function(w) { w.el.classList.remove('active'); });
    item.el.classList.add('active');
    active = id;
    renderTaskbar();
  }

  function setupDrag(el, data) {
    var bar = el.querySelector('.win-titlebar');
    if (!bar) return;
    var isDown = false, startX, startY, origLeft, origTop;
    function onDown(e) {
      focus(el.id);
      var rect = el.getBoundingClientRect();
      startX = e.clientX; startY = e.clientY;
      origLeft = rect.left; origTop = rect.top;
      isDown = true;
      bar.style.cursor = 'grabbing';
    }
    function onMove(e) {
      if (!isDown) return;
      var left = origLeft + (e.clientX - startX);
      var top = origTop + (e.clientY - startY);
      var maxX = window.innerWidth - 60;
      var maxY = window.innerHeight - 48 - 60;
      left = Math.max(-el.offsetWidth + 60, Math.min(maxX, left));
      top = Math.max(0, Math.min(maxY, top));
      el.style.left = left + 'px';
      el.style.top = top + 'px';
      var d = find(el.id);
      if (d) { d.left = left; d.top = top; }
    }
    function onUp(e) {
      if (isDown) {
        isDown = false;
        bar.style.cursor = '';
        var d = find(el.id);
        if (d) saveState(d);
      }
    }
    bar.addEventListener('pointerdown', onDown);
    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
  }

  function escapeHtml(s) {
    if (typeof s !== 'string') return '';
    return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  }

  function close(id) {
    var item = find(id);
    if (!item) return;
    item.el.remove();
    for (var i = 0; i < list.length; i++) {
      if (list[i].id === id) { list.splice(i, 1); break; }
    }
    localStorage.removeItem(sk(id));
    renderTaskbar();
    if (active === id) {
      var next = list.length ? list[list.length - 1] : null;
      if (next && !next.min) focus(next.id);
      else active = null;
    }
  }

  // 根据视口计算最大可用尺寸（减去左侧栏 280px、底部任务栏 48px、边距）
  function calcMaxDims() {
    return {
      w: window.innerWidth - 300,   // 预留左侧栏 + 边距
      h: window.innerHeight - 48 - 40, // 预留任务栏 + 边距
    };
  }

  return {
    list: list,

    create: function(title, html, w, h, id) {
      if (!id) id = 'w' + Date.now() + '_' + (Math.random() * 1e9 | 0);
      if (find(id)) { focus(id); return find(id); }

      var max = calcMaxDims();
      var saved = loadState(id);

      // 尺寸：优先用保存的，否则用传入值，上限不超过视口 92%
      var width = saved ? saved.width : Math.min(w || 560, Math.floor(max.w * 0.92));
      var height = saved ? saved.height : Math.min(h || 320, Math.floor(max.h * 0.88));
      // 确保不小于最小值
      width = Math.max(280, width);
      height = Math.max(150, height);
      // 确保不超出视口
      width = Math.min(width, max.w);
      height = Math.min(height, max.h);

      // 位置：靠左排列，但确保不超出右侧
      var cascade = Math.min(list.length * 28, max.w - width - 20);
      var left = saved ? saved.left : Math.max(10, cascade);
      var top = saved ? saved.top : Math.max(10, 20 + list.length * 28);
      top = Math.min(top, max.h - height + 20);
      var minimized = saved ? saved.minimized : false;

      var el = document.createElement('div');
      el.id = id;
      el.className = 'window' + (minimized ? '' : ' active');
      el.style.cssText = 'left:' + left + 'px;top:' + top + 'px;width:' + width + 'px;height:' + height + 'px;z-index:' + (++z) + ';display:' + (minimized ? 'none' : 'flex') + ';';

      el.innerHTML =
        '<div class="win-titlebar">' +
          '<span class="win-title">' + escapeHtml(title) + '</span>' +
          '<button class="win-btn" data-act="min">─</button>' +
          '<button class="win-btn close" data-act="close">✕</button>' +
        '</div>' +
        '<div class="win-body">' + html + '</div>';

      document.body.appendChild(el);

      var data = {
        id: id, el: el, title: title, z: z,
        min: minimized, left: left, top: top,
        width: width, height: height
      };
      list.push(data);

      if (!minimized) {
        active = id;
        list.forEach(function(w) { w.el.classList.remove('active'); });
        el.classList.add('active');
      }

      renderTaskbar();
      setupDrag(el, data);

      el.querySelector('[data-act="min"]').onclick = function(e) {
        e.stopPropagation();
        data.min = true;
        el.style.display = 'none';
        saveState(data);
        renderTaskbar();
        var next = null;
        for (var i = 0; i < list.length; i++) {
          if (!list[i].min) { next = list[i]; break; }
        }
        if (next) focus(next.id);
      };

      el.querySelector('[data-act="close"]').onclick = function(e) {
        e.stopPropagation();
        close(id);
      };

      return data;
    },

    close: close,
    focus: focus,
    find: find,
    renderTaskbar: renderTaskbar,
    escapeHtml: escapeHtml,
  };
})();
