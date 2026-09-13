import { create } from "zustand";
import { loginApi, type LoginRequest, type UserResponse } from "../api/auth";

interface User {
  id: string;
  username: string;
  email: string;
  display_name: string;
  role: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  accessToken: string | null;
  refreshToken: string | null;
  loginLoading: boolean;
  loginError: string | null;
  initReady: boolean; // 初始化完成标志

  login: (data: LoginRequest) => Promise<boolean>;
  initAuth: () => Promise<void>;
  setAuth: (user: User, accessToken: string, refreshToken: string) => void;
  clearAuth: () => void;
  clearLoginError: () => void;
}

function persistUser(user: User) {
  try {
    localStorage.setItem("ccms_user", JSON.stringify(user));
  } catch { /* ignore */ }
}

function loadUser(): User | null {
  try {
    const raw = localStorage.getItem("ccms_user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

const storedToken = localStorage.getItem("access_token");
const storedRefresh = localStorage.getItem("refresh_token");
const hasToken = !!(storedToken || storedRefresh);

export const useAuthStore = create<AuthState>((set) => ({
  // 从 localStorage 恢复 token，但先不认定已认证，等 initAuth 校验
  user: loadUser(),
  isAuthenticated: false, // 需要 initAuth 验证后才为 true
  accessToken: storedToken,
  refreshToken: storedRefresh,
  loginLoading: false,
  loginError: null,
  initReady: false,

  /** 应用启动时调用 — 校验已有 token 是否有效并恢复会话 */
  initAuth: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      set({ initReady: true });
      return;
    }

    try {
      const { default: apiClient } = await import("../api/client");
      const meRes = await apiClient.get<UserResponse>("/auth/me");
      const u = meRes.data;
      const user: User = {
        id: u.id,
        username: u.username,
        email: u.email,
        display_name: u.display_name,
        role: u.role,
      };
      persistUser(user);
      set({
        user,
        isAuthenticated: true,
        initReady: true,
      });
    } catch (err: any) {
      // 只有明确的 401 才清除 token；网络错误则保留 token 尝试下次恢复
      if (err?.response?.status === 401) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        localStorage.removeItem("ccms_user");
        set({
          user: null,
          isAuthenticated: false,
          accessToken: null,
          refreshToken: null,
          initReady: true,
        });
      } else {
        // 网络错误或后端不可达：保留 token，用缓存用户显示
        const cachedUser = loadUser();
        if (cachedUser) {
          set({ user: cachedUser, isAuthenticated: true, initReady: true });
        } else {
          set({ initReady: true });
        }
      }
    }
  },

  login: async (data: LoginRequest) => {
    set({ loginLoading: true, loginError: null });
    try {
      const res = await loginApi(data);
      const { access_token, refresh_token } = res.data;
      localStorage.setItem("access_token", access_token);
      localStorage.setItem("refresh_token", refresh_token);

      // 获取用户信息
      try {
        const { default: apiClient } = await import("../api/client");
        const meRes = await apiClient.get<UserResponse>("/auth/me");
        const u = meRes.data;
        const user: User = {
          id: u.id,
          username: u.username,
          email: u.email,
          display_name: u.display_name,
          role: u.role,
        };
        persistUser(user);
        set({
          user,
          isAuthenticated: true,
          accessToken: access_token,
          refreshToken: refresh_token,
          loginLoading: false,
        });
      } catch {
        // 即使获取用户信息失败也保留 token
        set({
          isAuthenticated: true,
          accessToken: access_token,
          refreshToken: refresh_token,
          loginLoading: false,
        });
      }
      return true;
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "登录失败";
      set({ loginLoading: false, loginError: msg });
      return false;
    }
  },

  setAuth: (user, accessToken, refreshToken) => {
    localStorage.setItem("access_token", accessToken);
    localStorage.setItem("refresh_token", refreshToken);
    persistUser(user);
    set({ user, isAuthenticated: true, accessToken, refreshToken });
  },

  clearAuth: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("ccms_user");
    set({
      user: null,
      isAuthenticated: false,
      accessToken: null,
      refreshToken: null,
    });
  },

  clearLoginError: () => set({ loginError: null }),
}));

// 监听 auth-expired 事件
if (typeof window !== "undefined") {
  window.addEventListener("auth-expired", () => {
    useAuthStore.getState().clearAuth();
  });
}
