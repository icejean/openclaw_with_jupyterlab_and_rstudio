// ==UserScript==
// @name         JupyterLab Auto-Reload (OpenClaw MCP)
// @namespace    https://openclaw.ai
// @version      0.1.0
// @description  自动刷新 JupyterLab Notebook（检测文件变化后自动 reload）
// @author       🦞 虾一跳
// @match        *://*/lab*
// @match        *://*/user/*/lab*
// @icon         https://jupyter.org/favicon.ico
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    // ---- 配置 ----
    const POLL_MS = 2000;  // 每 2 秒检测一次

    // ---- 获取 notebook 路径 ----
    function getNotebookPath() {
        // 方法 1: jupyter-config-data
        const cfg = document.querySelector('#jupyter-config-data');
        if (cfg) {
            try {
                const data = JSON.parse(cfg.textContent);
                const url = data.pageUrl || data.settings?.pageUrl || '';
                const m = url.match(/lab\/tree\/(.+?)(\?|$)/);
                if (m) return decodeURIComponent(m[1]);
            } catch(e) {}
        }
        // 方法 2: URL
        const m = location.href.match(/\/lab\/tree\/(.+?)(\?|#|$)/);
        return m ? decodeURIComponent(m[1]) : null;
    }

    // ---- 获取 baseUrl 和 token ----
    function getServerConfig() {
        const cfg = document.querySelector('#jupyter-config-data');
        if (!cfg) return { baseUrl: '/', token: '' };
        try {
            const data = JSON.parse(cfg.textContent);
            return {
                baseUrl: data.baseUrl || '/',
                token: data.token || data.settings?.token || ''
            };
        } catch(e) {
            return { baseUrl: '/', token: '' };
        }
    }

    // ---- 启动 ----
    const nbPath = getNotebookPath();
    if (!nbPath) {
        console.log('[Auto-Reload] 未检测到 Notebook 页面');
        return;
    }

    const { baseUrl, token } = getServerConfig();
    let lastMod = null;

    console.log(`%c🔁 Auto-Reload 已启动`, 'font-size:14px;font-weight:bold');
    console.log(`   跟踪: ${nbPath.split('/').pop()}`);
    console.log(`   间隔: ${POLL_MS/1000}s`);

    setInterval(async () => {
        try {
            const resp = await fetch(`${baseUrl}api/contents/${nbPath}`, {
                headers: token ? { Authorization: `token ${token}` } : {},
                credentials: 'include'
            });
            if (!resp.ok) return;
            const data = await resp.json();
            const newMod = data.last_modified;

            if (lastMod && newMod !== lastMod) {
                console.log('🔄 文件已变化，刷新 Notebook...');
                location.reload();
            }
            lastMod = newMod;
        } catch(e) {
            // 忽略错误
        }
    }, POLL_MS);
})();
