// 统一请求封装：uni.request → Promise，自动带 token，解包 {code,message,data}
// H5 走 vite/nginx 反代（相对路径）；小程序/App 请将 BASE_URL 改为后端完整地址
const BASE_URL = "";
const TOKEN_KEY = "itsm_token";

export function getToken(): string {
  return uni.getStorageSync(TOKEN_KEY) || "";
}
export function setToken(t: string) {
  uni.setStorageSync(TOKEN_KEY, t);
}
export function clearToken() {
  uni.removeStorageSync(TOKEN_KEY);
}

interface ApiResp<T = any> {
  code: number;
  message: string;
  data: T;
}

export function request<T = any>(options: {
  url: string;
  method?: "GET" | "POST" | "PUT" | "DELETE";
  data?: any;
}): Promise<T> {
  return new Promise((resolve, reject) => {
    uni.request({
      url: BASE_URL + options.url,
      method: options.method || "GET",
      data: options.data,
      header: {
        "Content-Type": "application/json",
        Authorization: getToken() ? `Bearer ${getToken()}` : "",
      },
      success: (res: any) => {
        const body = res.data as ApiResp<T>;
        if (body && body.code === 0) {
          resolve(body.data);
        } else {
          const msg = (body && body.message) || "请求失败";
          uni.showToast({ title: msg, icon: "none" });
          reject(body);
        }
      },
      fail: (err) => {
        uni.showToast({ title: "网络错误", icon: "none" });
        reject(err);
      },
    });
  });
}

// 图片上传（multipart）→ 返回 {url}
export function uploadImage(filePath: string): Promise<{ url: string }> {
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: BASE_URL + "/api/v1/uploads",
      filePath,
      name: "file",
      header: { Authorization: `Bearer ${getToken()}` },
      success: (res) => {
        try {
          const body = JSON.parse(res.data) as ApiResp<{ url: string }>;
          if (body.code === 0) resolve(body.data);
          else reject(body);
        } catch (e) {
          reject(e);
        }
      },
      fail: reject,
    });
  });
}
