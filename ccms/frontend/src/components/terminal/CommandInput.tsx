import { useState, useRef, useEffect, type KeyboardEvent } from "react";
import { Send, Loader, Square } from "lucide-react";
import { useTerminalStore } from "../../store/terminalStore";

export default function CommandInput() {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const isExecuting = useTerminalStore((s) => s.isExecuting);
  const executeCommand = useTerminalStore((s) => s.executeCommand);
  const cancelRunningCommand = useTerminalStore((s) => s.cancelRunningCommand);
  const commandHistory = useTerminalStore((s) => s.commandHistory);
  const historyIndex = useTerminalStore((s) => s.historyIndex);
  const decrementHistory = useTerminalStore((s) => s.decrementHistory);
  const incrementHistory = useTerminalStore((s) => s.incrementHistory);

  // 聚焦输入框（仅初始加载）
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // ArrowUp/Down 历史记录同步
  useEffect(() => {
    if (historyIndex >= 0 && historyIndex < commandHistory.length) {
      setInput(commandHistory[historyIndex].command);
    } else if (historyIndex < 0) {
      setInput("");
    }
  }, [historyIndex, commandHistory]);

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      const cmd = input.trim();
      if (cmd && !isExecuting) {
        setInput("");
        executeCommand(cmd);
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      decrementHistory();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      incrementHistory();
    }
  };

  const handleSubmit = () => {
    const cmd = input.trim();
    if (cmd && !isExecuting) {
      setInput("");
      executeCommand(cmd);
    }
  };

  const handleCancel = () => {
    cancelRunningCommand();
  };

  return (
    <div className="h-12 bg-surface-200 border-t border-gray-700 flex items-center px-3 gap-2 shrink-0">
      {/* 提示符 */}
      <span className="text-green-400 font-mono text-sm shrink-0 select-none">
        {isExecuting ? (
          <Loader size={14} className="animate-spin text-yellow-400" />
        ) : (
          "$"
        )}
      </span>

      {/* 输入框 */}
      <input
        ref={inputRef}
        type="text"
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={isExecuting ? "命令执行中..." : "输入指令发给 Claude Code，如: 分析代码 | ! 开头执行原始命令"}
        disabled={isExecuting}
        className="flex-1 bg-transparent border-none outline-none text-white font-mono text-sm placeholder-gray-600 disabled:opacity-50"
        spellCheck={false}
        autoComplete="off"
      />

      {/* 按钮 */}
      {isExecuting ? (
        <button
          onClick={handleCancel}
          className="p-1.5 rounded hover:bg-red-700 text-red-400 hover:text-red-300 transition-colors shrink-0"
          title="取消执行"
        >
          <Square size={15} />
        </button>
      ) : (
        <button
          onClick={handleSubmit}
          disabled={!input.trim()}
          className="p-1.5 rounded hover:bg-primary-600 text-gray-400 hover:text-white transition-colors disabled:opacity-30 disabled:cursor-not-allowed shrink-0"
          title="执行命令 (Enter)"
        >
          <Send size={15} />
        </button>
      )}
    </div>
  );
}
