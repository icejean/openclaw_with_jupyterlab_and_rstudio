import { JupyterFrontEndPlugin } from '@jupyterlab/application';
/**
 * 插件: 将 MCP 等外部客户端发起的 kernel 执行结果显示到 Console
 *
 * v0.1.1: 修复 currentChanged 多次触发导致重复注册 IOPub 监听器的问题。
 * JupyterLab 的 FocusTracker/DocumentWidgetTracker 链式传递信号，
 * 导致 `onKernelChanged` 被多次调用，每个调用都注册一个 IOPub 监听器。
 * 修复：用 `currentIOPubHandler` 变量跟踪当前监听器，注册新监听器前
 * 先断开旧的，确保始终只有 1 个活跃监听器。
 */
declare const consoleAdoptPlugin: JupyterFrontEndPlugin<void>;
export default consoleAdoptPlugin;
