// 🔁 JupyterLab Auto-Reload — 粘贴到浏览器控制台 (F12 → Console) 按回车
// 功能：OpenClaw 往 Notebook 写入 Cell 后，自动检测并刷新当前 Notebook 页面

(async () => {
  // 1. 获取配置
  const cfg = JSON.parse(document.querySelector('#jupyter-config-data').textContent);
  const baseUrl = cfg.baseUrl || '/';
  const token = cfg.token || '';

  // 2. 获取当前 notebook 路径
  const pathMatch = cfg.pageUrl?.match(/lab\/tree\/(.+?)(\?|$)/)
    || window.location.href.match(/\/lab\/tree\/(.+?)(\?|#|$)/);
  const nbPath = pathMatch ? decodeURIComponent(pathMatch[1]) : null;

  if (!nbPath) { console.error('❌ 无法识别当前 Notebook 路径'); return; }

  // 3. 轮询检测文件变化
  let lastMod = null;
  const POLL_MS = 2000;

  console.log(`🔁 Auto-Reload 已启动 — 跟踪: ${nbPath.split('/').pop()}`);
  console.log(`   每 ${POLL_MS/1000} 秒检测一次，检测到变化自动刷新页面`);

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
        console.log('🔄 检测到文件变化，刷新 Notebook...');
        window.location.reload();
      }
      lastMod = newMod;
    } catch (e) { /* ignore */ }
  }, POLL_MS);
})();
