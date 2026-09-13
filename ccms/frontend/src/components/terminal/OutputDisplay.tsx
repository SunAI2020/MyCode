import { useEffect, useRef } from "react";
import { useTerminalStore, type CommandStatus } from "../../store/terminalStore";
import { useAuthStore } from "../../store/authStore";
import { LogIn } from "lucide-react";

function statusBadge(status: CommandStatus) {
  switch (status) {
    case "running":
      return (
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-500/20 text-yellow-400">
          运行中
        </span>
      );
    case "completed":
      return null;
    case "error":
      return (
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400">
          错误
        </span>
      );
    case "cancelled":
      return (
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-gray-500/20 text-gray-400">
          已取消
        </span>
      );
  }
}

export default function OutputDisplay() {
  const commandHistory = useTerminalStore((s) => s.commandHistory);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const scrollRef = useRef<HTMLDivElement>(null);

  // 自动滚到底部
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [commandHistory]);

  return (
    <div
      ref={scrollRef}
      className="flex-1 overflow-y-auto p-4 font-mono text-sm bg-surface-300"
    >
      {commandHistory.length === 0 ? (
        /* 空状态 */
        <div className="flex flex-col items-center justify-center h-full text-gray-600 select-none">
          <div className="text-4xl mb-3">&gt;_</div>
          <p className="text-sm mb-1 text-gray-400">Claude Code 命令行</p>
          <p className="text-xs mb-4">
            {isAuthenticated
              ? "输入 claude 命令，AI 将自动分析并执行任务"
              : "请先登录后再执行命令"}
          </p>
          {!isAuthenticated ? (
            <div className="flex items-center gap-2 text-xs text-yellow-500 bg-yellow-500/10 rounded px-3 py-2 mb-4">
              <LogIn size={14} />
              点击右上角「登录」按钮完成认证
            </div>
          ) : (
            <div className="mt-5 text-xs space-y-1 text-gray-700">
              <p className="text-gray-500">Claude Code 命令示例：</p>
              <p className="text-green-400/70">  claude "帮我分析 main.py 的代码结构"</p>
              <p className="text-green-400/70">  claude --model claude-sonnet-4-6 "重构这个函数"</p>
              <p className="text-green-400/70">  claude "查找项目中的安全漏洞"</p>
              <p className="text-green-400/70">  claude --working-dir D:/project "分析项目"</p>
            </div>
          )}
        </div>
      ) : (
        /* 命令历史 */
        <div className="space-y-4">
          {commandHistory.map((entry) => (
            <div key={entry.id}>
              {/* 命令提示符 */}
              <div className="flex items-center gap-2">
                <span className="text-green-400">$</span>
                <span className="text-white">{entry.command}</span>
                {statusBadge(entry.status)}
              </div>
              {/* 输出 */}
              {entry.output && (
                <pre className="mt-1 text-gray-300 whitespace-pre-wrap break-all text-[13px] leading-relaxed pl-4 border-l-2 border-gray-700">
                  {entry.output}
                </pre>
              )}
              {entry.status === "running" && !entry.output && (
                <div className="mt-1 pl-4 border-l-2 border-yellow-500/30 text-gray-500 text-[13px] animate-pulse">
                  执行中...
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
