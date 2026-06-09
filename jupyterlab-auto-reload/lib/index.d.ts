import { JupyterFrontEndPlugin } from '@jupyterlab/application';
/**
 * 自动刷新 Notebook 插件
 *
 * 每 3 秒检查一次当前 Notebook 文件在服务器上的 last_modified 时间戳。
 * 如果发现文件被外部修改（如 OpenClaw 的 MCP Server 写入），
 * 且用户没有未保存的修改，自动执行 context.revert() 刷新 Notebook。
 */
declare const autoReloadPlugin: JupyterFrontEndPlugin<void>;
export default autoReloadPlugin;
