import { useState, type FormEvent } from "react";
import { X, LogIn, Loader } from "lucide-react";
import { useAuthStore } from "../../store/authStore";

interface Props {
  onClose: () => void;
}

export default function LoginModal({ onClose }: Props) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");

  const login = useAuthStore((s) => s.login);
  const loginLoading = useAuthStore((s) => s.loginLoading);
  const loginError = useAuthStore((s) => s.loginError);
  const clearLoginError = useAuthStore((s) => s.clearLoginError);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (isRegister) {
      // 注册后自动登录
      try {
        const { registerApi } = await import("../../api/auth");
        await registerApi({
          username,
          email,
          password,
          display_name: displayName,
        });
      } catch (err: unknown) {
        const msg =
          err instanceof Error ? err.message : "注册失败";
        useAuthStore.setState({ loginError: msg });
        return;
      }
    }
    await login({ username: username.trim(), password });
    if (useAuthStore.getState().isAuthenticated) {
      onClose();
    }
  };

  const switchMode = () => {
    setIsRegister(!isRegister);
    clearLoginError();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-surface-200 border border-gray-600 rounded-lg w-[400px] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-gray-700">
          <h3 className="text-base font-semibold text-white flex items-center gap-2">
            <LogIn size={18} className="text-primary-400" />
            {isRegister ? "注册账号" : "登录 CCMS"}
          </h3>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white"
          >
            <X size={16} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          <div>
            <label className="block text-xs text-gray-400 mb-1">用户名</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full bg-surface-300 border border-gray-600 rounded px-3 py-2 text-sm text-white outline-none focus:border-primary-500"
              placeholder="输入用户名"
              required
              autoFocus
            />
          </div>

          {isRegister && (
            <>
              <div>
                <label className="block text-xs text-gray-400 mb-1">邮箱</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-surface-300 border border-gray-600 rounded px-3 py-2 text-sm text-white outline-none focus:border-primary-500"
                  placeholder="your@email.com"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">显示名称</label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="w-full bg-surface-300 border border-gray-600 rounded px-3 py-2 text-sm text-white outline-none focus:border-primary-500"
                  placeholder="你的名字"
                  required
                />
              </div>
            </>
          )}

          <div>
            <label className="block text-xs text-gray-400 mb-1">密码</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-surface-300 border border-gray-600 rounded px-3 py-2 text-sm text-white outline-none focus:border-primary-500"
              placeholder="输入密码"
              required
            />
          </div>

          {loginError && (
            <div className="text-xs text-red-400 bg-red-500/10 rounded px-3 py-2">
              {loginError}
            </div>
          )}

          <button
            type="submit"
            disabled={loginLoading}
            className="w-full py-2 rounded bg-primary-600 text-white text-sm font-medium hover:bg-primary-500 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loginLoading ? (
              <>
                <Loader size={14} className="animate-spin" />
                处理中...
              </>
            ) : isRegister ? (
              "注册并登录"
            ) : (
              "登录"
            )}
          </button>

          <p className="text-center text-xs text-gray-500">
            {isRegister ? "已有账号？" : "没有账号？"}
            <button
              type="button"
              onClick={switchMode}
              className="text-primary-400 hover:text-primary-300 ml-1"
            >
              {isRegister ? "去登录" : "去注册"}
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}
