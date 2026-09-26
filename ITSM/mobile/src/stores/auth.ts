// 轻量认证状态（reactive + storage 持久化）
import { reactive } from "vue";
import { request, getToken, setToken, clearToken } from "../api";

export const auth = reactive({
  token: getToken(),
  user: null as any,

  async login(username: string, password: string) {
    const data = await request<{ access_token: string; user: any }>({
      url: "/api/v1/auth/login",
      method: "POST",
      data: { username, password },
    });
    setToken(data.access_token);
    this.token = data.access_token;
    this.user = data.user;
    return data;
  },

  async fetchMe() {
    this.user = await request<any>({ url: "/api/v1/auth/me" });
    return this.user;
  },

  logout() {
    clearToken();
    this.token = "";
    this.user = null;
    uni.reLaunch({ url: "/pages/login/login" });
  },
});
