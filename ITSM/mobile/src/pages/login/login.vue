<template>
  <view class="wrap">
    <view class="brand">IT运维集中管控平台</view>
    <view class="sub">移动端 · 服务人员 / 管理员</view>
    <input v-model="username" placeholder="用户名" class="ipt" />
    <input v-model="password" password placeholder="密码" class="ipt" />
    <button class="btn" :loading="loading" @click="onLogin">登 录</button>
    <view class="hint">人脸/指纹快捷登录预留（设备级生物识别保护本地凭证）</view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { auth } from "../../stores/auth";

const username = ref("");
const password = ref("");
const loading = ref(false);

async function onLogin() {
  if (!username.value || !password.value) {
    uni.showToast({ title: "请输入账号密码", icon: "none" });
    return;
  }
  loading.value = true;
  try {
    await auth.login(username.value, password.value);
    uni.reLaunch({ url: "/pages/index/index" });
  } catch (e) {
    /* 错误提示已由 request 统一处理 */
  } finally {
    loading.value = false;
  }
}
</script>

<style>
.wrap { padding: 120rpx 60rpx; }
.brand { font-size: 42rpx; font-weight: 700; text-align: center; color: #0a3d91; }
.sub { text-align: center; color: #8c959f; font-size: 26rpx; margin: 12rpx 0 80rpx; }
.ipt { border: 1rpx solid #e1e4e8; border-radius: 12rpx; padding: 24rpx; margin-bottom: 24rpx; background: #fff; }
.btn { background: #0a3d91; color: #fff; border-radius: 12rpx; margin-top: 40rpx; }
.hint { margin-top: 40rpx; text-align: center; color: #b0b6bd; font-size: 22rpx; }
</style>
