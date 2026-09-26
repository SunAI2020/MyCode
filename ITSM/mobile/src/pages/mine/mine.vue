<template>
  <view class="wrap">
    <view class="card">
      <view class="name">{{ auth.user?.name || "—" }}</view>
      <view class="sub">@{{ auth.user?.username }}</view>
    </view>
    <view class="card">
      <view class="row"><text class="lbl">角色</text><text>{{ roles }}</text></view>
      <view class="row"><text class="lbl">部门</text><text>{{ auth.user?.dept || "—" }}</text></view>
    </view>
    <button class="logout" @click="onLogout">退出登录</button>
  </view>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { auth } from "../../stores/auth";

const roles = computed(() =>
  (auth.user?.roles || []).map((r: any) => r.name).join(" / ") || "—"
);

onShow(() => {
  if (!auth.user) auth.fetchMe().catch(() => {});
});

function onLogout() {
  auth.logout();
}
</script>

<style>
.wrap { padding: 24rpx; }
.card { background: #fff; border-radius: 16rpx; padding: 32rpx; margin-bottom: 24rpx; }
.name { font-size: 40rpx; font-weight: 700; }
.sub { color: #8c959f; margin-top: 8rpx; }
.row { display: flex; justify-content: space-between; padding: 12rpx 0; font-size: 28rpx; }
.lbl { color: #8c959f; }
.logout { background: #e5484d; color: #fff; border-radius: 12rpx; }
</style>
