import {
  Archive,
  Bot,
  Calendar,
  ChevronLeft,
  ChevronRight,
  Code,
  FolderOpen,
  MessageSquare,
  Monitor,
  Puzzle,
  Server,
  Settings,
} from "lucide-react";

interface SidebarProps {
  collapsed: boolean;
  activePanel: string | null;
  onToggle: () => void;
  onPanelSelect: (panel: string) => void;
}

const NAV_ITEMS = [
  { id: "projects", label: "项目管理", icon: FolderOpen },
  { id: "sessions", label: "会话管理", icon: MessageSquare },
  { id: "agents", label: "Agent 设置", icon: Bot },
  { id: "nodes", label: "节点管理", icon: Server },
  { id: "skills", label: "技能管理", icon: Puzzle },
  { id: "cron", label: "定时任务", icon: Calendar },
  { id: "settings", label: "系统设置", icon: Settings },
];

export default function LeftSidebar({
  collapsed,
  activePanel,
  onToggle,
  onPanelSelect,
}: SidebarProps) {
  return (
    <aside
      className={`flex flex-col bg-surface-200 border-r border-gray-700 transition-all duration-200 ${
        collapsed ? "w-14" : "w-60"
      }`}
    >
      {/* Logo + 折叠按钮 */}
      <div className="flex items-center justify-between p-3 border-b border-gray-700">
        {!collapsed && (
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded bg-primary-600 flex items-center justify-center">
              <Code size={14} className="text-white" />
            </div>
            <span className="font-bold text-sm text-white">CCMS</span>
          </div>
        )}
        <button
          onClick={onToggle}
          className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
          title={collapsed ? "展开侧边栏" : "折叠侧边栏"}
        >
          {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      {/* 导航项 */}
      <nav className="flex-1 py-2 overflow-y-auto">
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            onClick={() => onPanelSelect(item.id)}
            className={`w-full flex items-center gap-3 px-3 py-2.5 text-sm transition-colors ${
              activePanel === item.id
                ? "bg-primary-600/20 text-primary-400 border-r-2 border-primary-500"
                : "text-gray-400 hover:text-white hover:bg-gray-700/50"
            }`}
            title={collapsed ? item.label : undefined}
          >
            <item.icon size={18} />
            {!collapsed && <span>{item.label}</span>}
          </button>
        ))}
      </nav>

      {/* 底部信息 */}
      {!collapsed && (
        <div className="p-3 border-t border-gray-700 text-xs text-gray-500">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500" />
            <span>系统运行中</span>
          </div>
          <div className="mt-1">CCMS v0.1.0</div>
        </div>
      )}
    </aside>
  );
}
