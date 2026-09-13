import { create } from "zustand";
import {
  cancelSession as cancelSessionApi,
  executeCommand as executeCommandApi,
  getSession,
  type SessionResponse,
} from "../api/terminal";

// ── Types ──

export type CommandStatus = "running" | "completed" | "error" | "cancelled";

export interface CommandEntry {
  id: string;
  command: string;
  output: string;
  status: CommandStatus;
  startedAt: string;
}

interface TerminalState {
  // 工作目录
  workingDirectory: string;

  // 命令历史
  commandHistory: CommandEntry[];
  historyIndex: number;

  // 当前会话
  currentSessionId: string | null;
  isExecuting: boolean;

  // 轮询定时器
  _pollTimer: ReturnType<typeof setInterval> | null;

  // ── Actions ──
  setWorkingDirectory: (dir: string) => void;
  executeCommand: (command: string) => Promise<void>;
  cancelRunningCommand: () => Promise<void>;
  addCommand: (entry: CommandEntry) => void;
  updateCommandOutput: (
    id: string,
    output: string,
    status: CommandStatus,
  ) => void;
  setCurrentSession: (sessionId: string | null) => void;
  clearHistory: () => void;
  setHistoryIndex: (index: number) => void;
  decrementHistory: () => void;
  incrementHistory: () => void;
}

// ── Helpers ──

function getSavedDir(): string {
  try {
    return localStorage.getItem("ccms_working_dir") || "D:\\";
  } catch {
    return "D:\\";
  }
}

function saveDir(dir: string) {
  try {
    localStorage.setItem("ccms_working_dir", dir);
  } catch {
    // ignore
  }
}

/**
 * 将用户输入转换为最终 shell 命令。
 * - 以 `!` 开头：去掉 `!` 后作为原始 shell 命令执行
 * - 其它：自动包装为 claude -p "..." 发送给 Claude Code
 */
function wrapCommand(input: string): string {
  if (input.startsWith("!")) {
    return input.slice(1).trim();
  }
  // 转义双引号，防止 shell 注入
  const escaped = input.replace(/"/g, '\\"');
  return `claude -p "${escaped}"`;
}

// ── Store ──

export const useTerminalStore = create<TerminalState>((set, get) => ({
  workingDirectory: getSavedDir(),
  commandHistory: [],
  historyIndex: -1,
  currentSessionId: null,
  isExecuting: false,
  _pollTimer: null,

  setWorkingDirectory: (dir: string) => {
    saveDir(dir);
    set({ workingDirectory: dir });
  },

  executeCommand: async (command: string) => {
    const { workingDirectory } = get();

    // 停止之前的轮询
    const prevTimer = get()._pollTimer;
    if (prevTimer) clearInterval(prevTimer);

    // 自动包装为 claude 命令（! 前缀则原样执行 shell）
    const shellCommand = wrapCommand(command);

    try {
      const res = await executeCommandApi(shellCommand, workingDirectory);
      const sessionId = res.data.session_id;

      const entry: CommandEntry = {
        id: sessionId,
        command,           // 历史记录显示用户原始输入
        output: "",
        status: "running",
        startedAt: new Date().toISOString(),
      };

      set({
        currentSessionId: sessionId,
        isExecuting: true,
        commandHistory: [...get().commandHistory, entry],
        historyIndex: -1,
      });

      // 轮询输出
      const timer = setInterval(async () => {
        try {
          const sessionRes = await getSession(sessionId);
          const s: SessionResponse = sessionRes.data;

          get().updateCommandOutput(
            sessionId,
            s.output_buffer || "",
            s.status as CommandStatus,
          );

          if (s.status !== "active") {
            const t = get()._pollTimer;
            if (t) clearInterval(t);
            set({ isExecuting: false, _pollTimer: null });
          }
        } catch {
          // 轮询失败则继续
        }
      }, 500);

      set({ _pollTimer: timer });
    } catch (err: unknown) {
      const errorMsg =
        err instanceof Error ? err.message : "命令执行失败";
      const errorEntry: CommandEntry = {
        id: crypto.randomUUID(),
        command,
        output: `[错误] ${errorMsg}`,
        status: "error",
        startedAt: new Date().toISOString(),
      };
      set({
        isExecuting: false,
        commandHistory: [...get().commandHistory, errorEntry],
        historyIndex: -1,
      });
    }
  },

  cancelRunningCommand: async () => {
    const { currentSessionId } = get();
    if (!currentSessionId) return;

    const timer = get()._pollTimer;
    if (timer) clearInterval(timer);

    try {
      await cancelSessionApi(currentSessionId);
    } catch {
      // ignore
    }

    get().updateCommandOutput(currentSessionId, "", "cancelled");
    set({ isExecuting: false, _pollTimer: null });
  },

  addCommand: (entry: CommandEntry) =>
    set((s) => ({
      commandHistory: [...s.commandHistory, entry],
      historyIndex: -1,
    })),

  updateCommandOutput: (id: string, output: string, status: CommandStatus) =>
    set((s) => ({
      commandHistory: s.commandHistory.map((e) =>
        e.id === id ? { ...e, output, status } : e,
      ),
    })),

  setCurrentSession: (sessionId) => set({ currentSessionId: sessionId }),

  clearHistory: () =>
    set({ commandHistory: [], historyIndex: -1 }),

  setHistoryIndex: (index: number) => set({ historyIndex: index }),

  decrementHistory: () => {
    const { commandHistory, historyIndex } = get();
    const max = commandHistory.length - 1;
    if (max < 0) return;
    const newIdx = historyIndex < 0 ? max : Math.max(0, historyIndex - 1);
    set({ historyIndex: newIdx });
  },

  incrementHistory: () => {
    const { commandHistory, historyIndex } = get();
    const max = commandHistory.length - 1;
    if (max < 0) return;
    const newIdx = historyIndex < 0 ? -1 : Math.min(max, historyIndex + 1);
    if (newIdx >= max) {
      set({ historyIndex: -1 });
    } else {
      set({ historyIndex: newIdx });
    }
  },
}));
