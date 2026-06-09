import {
  JupyterFrontEnd,
  JupyterFrontEndPlugin
} from '@jupyterlab/application';

import { INotebookTracker } from '@jupyterlab/notebook';

/**
 * 自动刷新 Notebook 插件
 *
 * 每 3 秒检查一次当前 Notebook 文件在服务器上的 last_modified 时间戳。
 * 如果发现文件被外部修改（如 OpenClaw 的 MCP Server 写入），
 * 且用户没有未保存的修改，自动执行 context.revert() 刷新 Notebook。
 */
const autoReloadPlugin: JupyterFrontEndPlugin<void> = {
  id: 'jupyterlab-auto-reload:plugin',
  autoStart: true,
  requires: [INotebookTracker],
  activate: (
    app: JupyterFrontEnd,
    tracker: INotebookTracker
  ) => {
    const POLL_MS = 3000;
    const lastModified: { [path: string]: string } = {};

    setInterval(async () => {
      const current = tracker.currentWidget;
      if (!current) {
        return;
      }

      const context = current.context;
      if (!context || context.isDisposed) {
        return;
      }

      try {
        // 通过 app.serviceManager.contents 获取文件最新信息
        const contentsManager = app.serviceManager.contents;
        if (!contentsManager) {
          return;
        }

        const model = await contentsManager.get(context.path);
        const serverTime: string = (model as any).last_modified || '';

        if (!serverTime) {
          return;
        }

        const path = context.path;

        // 首次检测：记录时间戳
        if (!lastModified[path]) {
          lastModified[path] = serverTime;
          return;
        }

        // 时间戳变化 → 文件被外部修改
        if (serverTime !== lastModified[path]) {
          lastModified[path] = serverTime;

          // 检查是否有未保存修改
          const modelAny = context.model as any;
          const isDirty = modelAny && modelAny.dirty;

          if (!isDirty) {
            console.log(
              `[auto-reload] File changed: ${path}, reloading...`
            );
            await context.revert();
            console.log(`[auto-reload] Reloaded.`);
          } else {
            console.log(
              `[auto-reload] File changed: ${path}, ` +
              `unsaved changes exist. Skipping.`
            );
          }
        }
      } catch (err) {
        // 忽略错误（Notebook 关闭等）
      }
    }, POLL_MS);
  }
};

export default autoReloadPlugin;
