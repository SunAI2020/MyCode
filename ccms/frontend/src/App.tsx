import { useEffect, useState } from "react";
import LeftSidebar from "./components/layout/LeftSidebar";
import TopBar from "./components/layout/TopBar";
import StatusBar from "./components/layout/StatusBar";
import TerminalPanel from "./components/terminal/TerminalPanel";
import { useAuthStore } from "./store/authStore";

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activePanel, setActivePanel] = useState<string | null>(null);
  const initAuth = useAuthStore((s) => s.initAuth);

  // 应用启动时恢复认证状态
  useEffect(() => {
    initAuth();
  }, [initAuth]);

  return (
    <div className="h-screen w-screen flex flex-col overflow-hidden bg-surface-300">
      {/* 顶部栏 */}
      <TopBar />

      <div className="flex flex-1 overflow-hidden">
        {/* 左侧边栏 */}
        <LeftSidebar
          collapsed={sidebarCollapsed}
          activePanel={activePanel}
          onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
          onPanelSelect={(panel) => {
            if (activePanel === panel) {
              setActivePanel(null);
            } else {
              setActivePanel(panel);
            }
          }}
        />

        {/* 主内容区 */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* 面板展开区 */}
          {activePanel && (
            <div className="bg-surface-200 border-b border-gray-700 p-4">
              <div className="text-sm text-gray-400">
                面板「{activePanel}」— 功能将在后续阶段实现
              </div>
            </div>
          )}

          {/* 主区域 */}
          <div className="flex-1 overflow-auto flex">
            <TerminalPanel />
          </div>
        </main>
      </div>

      {/* 底部状态栏 */}
      <StatusBar />
    </div>
  );
}
