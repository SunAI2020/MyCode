import axios from "axios";

const apiClient = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

// 请求拦截器 — 从 localStorage 读取 token（小程序场景回退）
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// 响应拦截器 — 处理 401 和连接错误
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // 清除过期 token
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      // 刷新页面状态（由 authStore 自行处理）
      window.dispatchEvent(new Event("auth-expired"));
    }

    // 改进错误消息：处理代理连接失败（后端未启动）的情况
    if (error.response?.status === 500 && !error.response?.data?.code) {
      // Vite 代理返回的空 500 通常是后端未启动
      error.message = "无法连接到后端服务，请确认服务器已启动";
    } else if (error.response?.data?.detail) {
      // 使用后端返回的详细错误消息
      error.message = error.response.data.detail;
    } else if (!error.response && error.code === "ECONNABORTED") {
      error.message = "请求超时，请检查网络连接";
    } else if (!error.response) {
      error.message = "无法连接到服务器，请确认后端服务已启动";
    }

    return Promise.reject(error);
  }
);

export default apiClient;
