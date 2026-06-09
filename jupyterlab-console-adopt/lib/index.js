import { IConsoleTracker } from '@jupyterlab/console';
/**
 * 插件: 将 MCP 等外部客户端发起的 kernel 执行结果显示到 Console
 *
 * v0.1.1: 修复 currentChanged 多次触发导致重复注册 IOPub 监听器的问题。
 * JupyterLab 的 FocusTracker/DocumentWidgetTracker 链式传递信号，
 * 导致 `onKernelChanged` 被多次调用，每个调用都注册一个 IOPub 监听器。
 * 修复：用 `currentIOPubHandler` 变量跟踪当前监听器，注册新监听器前
 * 先断开旧的，确保始终只有 1 个活跃监听器。
 */
const consoleAdoptPlugin = {
    id: 'jupyterlab-console-adopt:plugin',
    autoStart: true,
    requires: [IConsoleTracker],
    activate: (app, consoleTracker) => {
        console.log('[console-adopt] 插件已激活');
        consoleTracker.currentChanged.connect((_, consolePanel) => {
            if (!consolePanel)
                return;
            const consoleWidget = consolePanel.console;
            const sessionContext = consoleWidget.sessionContext;
            // v0.1.1: 跟踪当前 IOPub 监听器，防止重复注册
            let currentIOPubHandler = null;
            const onKernelChanged = () => {
                const kernel = sessionContext.session?.kernel;
                if (!kernel)
                    return;
                console.log('[console-adopt] 已连接到 kernel:', kernel.id);
                // v0.1.1: 断开旧的监听器再注册新的
                if (currentIOPubHandler) {
                    kernel.iopubMessage.disconnect(currentIOPubHandler);
                }
                const msgIdToCell = new Map();
                const onIOPubMessage = (_, msg) => {
                    const msgType = msg.header.msg_type;
                    if (msgType === 'execute_input') {
                        const content = msg.content;
                        const parentHeader = msg.parent_header;
                        const sessionId = parentHeader?.session || '';
                        // 跳过 Console 自身 session 的执行
                        if (sessionId === kernel.clientId)
                            return;
                        const code = content.code || '';
                        const msgId = parentHeader?.msg_id || '';
                        const execCount = content.execution_count;
                        if (!code || !msgId)
                            return;
                        console.log(`[console-adopt] 捕获外部执行 #${execCount}: session=${sessionId.slice(0, 8)}...`);
                        // 创建 CodeCell 并注入
                        const cell = consoleWidget.createCodeCell();
                        cell.model.sharedModel.setSource(code);
                        if (execCount) {
                            cell.model.executionCount = execCount;
                        }
                        // 伪 future，用于路由消息
                        const capturedOutputs = [];
                        const pseudoFuture = {
                            onIOPub: null,
                            onReply: null,
                            onStdin: null,
                            done: new Promise((resolve) => {
                                const checkDone = (_, m) => {
                                    if (m.parent_header?.msg_id === msgId &&
                                        m.header.msg_type === 'status' &&
                                        m.content.execution_state === 'idle') {
                                        kernel.iopubMessage.disconnect(checkDone);
                                        resolve();
                                    }
                                };
                                kernel.iopubMessage.connect(checkDone);
                            }),
                            dispose() {
                                this.onIOPub = null;
                                this.onReply = null;
                                this.onStdin = null;
                            },
                            registerMessageHook() { },
                            removeMessageHook() { },
                        };
                        // 设置到 OutputArea
                        cell.outputArea.future = pseudoFuture;
                        cell.outputHidden = false;
                        consoleWidget.addCell(cell, msgId);
                        // 转发后续输出
                        const forwardOutput = (_, m) => {
                            if (m.parent_header?.msg_id !== msgId)
                                return;
                            const mt = m.header.msg_type;
                            if (mt === 'execute_input' || mt === 'status') {
                                if (mt === 'status') {
                                    const state = m.content.execution_state;
                                    if (state === 'idle') {
                                        cell.model.executionState = 'idle';
                                    }
                                    else if (state === 'busy') {
                                        cell.model.executionState = 'running';
                                    }
                                }
                                return;
                            }
                            if (pseudoFuture.onIOPub) {
                                pseudoFuture.onIOPub(m);
                            }
                            else {
                                capturedOutputs.push(m);
                            }
                        };
                        kernel.iopubMessage.connect(forwardOutput);
                        // 等待 future.onIOPub 设置后回放
                        const checkAttached = setInterval(() => {
                            if (pseudoFuture.onIOPub) {
                                for (const cm of capturedOutputs) {
                                    pseudoFuture.onIOPub(cm);
                                }
                                capturedOutputs.length = 0;
                                clearInterval(checkAttached);
                            }
                        }, 50);
                        setTimeout(() => clearInterval(checkAttached), 3000);
                        pseudoFuture.done.then(() => {
                            kernel.iopubMessage.disconnect(forwardOutput);
                            msgIdToCell.delete(msgId);
                        });
                    }
                };
                // v0.1.1: 存引用再连接
                currentIOPubHandler = onIOPubMessage;
                kernel.iopubMessage.connect(onIOPubMessage);
                // 清理
                const cleanup = () => {
                    kernel.iopubMessage.disconnect(onIOPubMessage);
                };
                kernel.disposed.connect(cleanup);
                consoleWidget.disposed.connect(() => {
                    kernel.iopubMessage.disconnect(onIOPubMessage);
                    kernel.disposed.disconnect(cleanup);
                });
            };
            sessionContext.kernelChanged.connect(onKernelChanged);
            onKernelChanged();
        });
    }
};
export default consoleAdoptPlugin;
