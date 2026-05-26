/**
 * SSE 客户端——接收服务端推送的事件并更新 DOM。
 */
(function() {
    // SSE 连接状态指示器
    const statusEl = document.getElementById('sse-status');
    function setStatus(connected) {
        if (!statusEl) return;
        if (connected) {
            statusEl.classList.remove('disconnected');
            statusEl.querySelector('.dot').style.background = 'var(--down)';
            statusEl.childNodes[1].textContent = ' 实时连接中...';
        } else {
            statusEl.classList.add('disconnected');
            statusEl.querySelector('.dot').style.background = 'var(--up)';
            statusEl.childNodes[1].textContent = ' 连接断开，重连中...';
        }
    }

    function updatePanel(event, panelId, renderFn) {
        try {
            const data = JSON.parse(event.data);
            const panel = document.getElementById(panelId);
            if (panel) {
                panel.innerHTML = renderFn(data);
            }
        } catch(e) {
            console.warn('SSE parse error:', e);
        }
    }

    // 监听全局 SSE 事件
    document.body.addEventListener('htmx:sseMessage', function(evt) {
        const eventType = evt.detail.type;
        const panelId = evt.detail.elt?.id;
        // htmx 会自动处理 sse-swap，这里做额外处理
    });

    // 为每个 SSE 连接设置重连
    document.body.addEventListener('htmx:sseError', function(evt) {
        setStatus(false);
    });

    document.body.addEventListener('htmx:sseBeforeMessage', function() {
        setStatus(true);
    });
})();
