import { useState } from "react";
import { Bell, User, LogIn, LogOut } from "lucide-react";
import { useAuthStore } from "../../store/authStore";
import LoginModal from "./LoginModal";

export default function TopBar() {
  const [showLogin, setShowLogin] = useState(false);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const initReady = useAuthStore((s) => s.initReady);
  const user = useAuthStore((s) => s.user);
  const clearAuth = useAuthStore((s) => s.clearAuth);

  return (
    <>
      <header className="h-12 bg-surface-200 border-b border-gray-700 flex items-center justify-between px-4 shrink-0">
        {/* 标题 */}
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold text-white">
            Claude Code 管理系统中控台
          </h1>
          <span className="text-xs px-2 py-0.5 rounded bg-primary-600/20 text-primary-400">
            MVP v0.1.0
          </span>
          {isAuthenticated && user && (
            <span className="text-xs text-gray-500 ml-2">
              👤 {user.display_name}
            </span>
          )}
        </div>

        {/* 右侧操作 */}
        <div className="flex items-center gap-2">
          <button
            className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors relative"
            title="通知"
          >
            <Bell size={16} />
            <span className="absolute top-0.5 right-0.5 w-2 h-2 rounded-full bg-red-500" />
          </button>

          {isAuthenticated ? (
            <button
              onClick={clearAuth}
              className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors flex items-center gap-1.5"
              title="退出登录"
            >
              <span className="text-xs text-gray-500 hidden sm:inline">
                {user?.display_name || user?.username}
              </span>
              <LogOut size={14} />
            </button>
          ) : initReady ? (
            <button
              onClick={() => setShowLogin(true)}
              className="p-1.5 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors flex items-center gap-1.5"
              title="登录"
            >
              <span className="text-xs text-gray-500 hidden sm:inline">登录</span>
              <LogIn size={14} />
            </button>
          ) : (
            /* 初始化中，不显示按钮（避免闪烁） */
            <div className="w-8 h-8" />
          )}
        </div>
      </header>

      {/* 登录弹窗 */}
      {showLogin && <LoginModal onClose={() => setShowLogin(false)} />}
    </>
  );
}
