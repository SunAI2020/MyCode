import {
  Bot,
  Code,
  FolderOpen,
  Play,
  Terminal,
} from "lucide-react";

const QUICK_ACTIONS = [
  { id: "new-project", label: "新建项目", icon: FolderOpen, description: "创建新的代码项目" },
  { id: "new-agent", label: "创建 Agent", icon: Bot, description: "配置 AI 子 Agent" },
  { id: "open-editor", label: "代码编辑器", icon: Code, description: "打开 Monaco 编辑器" },
  { id: "open-terminal", label: "终端", icon: Terminal, description: "打开命令行终端" },
  { id: "quick-run", label: "快速执行", icon: Play, description: "运行脚本或命令" },
];

export default function WelcomeScreen() {
  return (
    <div className="h-full flex flex-col items-center justify-center p-8">
      {/* 主标题 */}
      <div className="text-center mb-10">
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center mx-auto mb-6 shadow-lg shadow-primary-500/20">
          <Bot size={40} className="text-white" />
        </div>
        <h2 className="text-2xl font-bold text-white mb-2">
          Claude Code 管理系统中控台
        </h2>
        <p className="text-gray-400 max-w-md mx-auto">
          AI 驱动的多 Agent 协同开发平台。管理项目、调度子 Agent、实时监控系统与资源。
        </p>
      </div>

      {/* 快捷操作卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-3 max-w-3xl w-full">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.id}
            className="flex flex-col items-center gap-3 p-5 rounded-xl bg-surface-200 border border-gray-700 hover:border-primary-500/50 hover:bg-surface-100 transition-all group"
          >
            <div className="w-12 h-12 rounded-lg bg-gray-700 flex items-center justify-center group-hover:bg-primary-600/20 transition-colors">
              <action.icon size={22} className="text-gray-400 group-hover:text-primary-400 transition-colors" />
            </div>
            <div className="text-center">
              <div className="text-sm font-medium text-white">{action.label}</div>
              <div className="text-xs text-gray-500 mt-0.5">{action.description}</div>
            </div>
          </button>
        ))}
      </div>

      {/* 状态概览 */}
      <div className="mt-10 grid grid-cols-4 gap-4 max-w-2xl w-full">
        {[
          { label: "项目", value: "0", color: "text-blue-400" },
          { label: "Agent", value: "0", color: "text-green-400" },
          { label: "今日 Token", value: "0", color: "text-yellow-400" },
          { label: "任务完成", value: "0", color: "text-purple-400" },
        ].map((stat) => (
          <div
            key={stat.label}
            className="text-center p-3 rounded-lg bg-surface-200 border border-gray-700"
          >
            <div className={`text-xl font-bold ${stat.color}`}>{stat.value}</div>
            <div className="text-xs text-gray-500 mt-1">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* 提示 */}
      <p className="mt-8 text-xs text-gray-600">
        从左侧边栏选择面板开始操作，或点击上方快捷入口
      </p>
    </div>
  );
}
