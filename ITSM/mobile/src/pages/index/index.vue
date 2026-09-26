<template>
  <view class="wrap">
    <view class="card">
      <view class="hello">{{ auth.user?.name || "—" }}，你好</view>
      <view class="sub">今日签到：{{ signedIn ? "已签到" : "未签到" }}</view>
    </view>

    <view class="grid">
      <view class="cell" @click="go('/pages/workorder/list')">
        <view class="num">{{ todoCount }}</view>
        <view class="label">{{ isCustomer ? "我的报障" : "工单总数" }}</view>
      </view>
      <view v-if="isService" class="cell" @click="go('/pages/checkin/checkin')">
        <view class="num">{{ signedIn ? "✓" : "去签到" }}</view>
        <view class="label">签到打卡</view>
      </view>
    </view>

    <view class="card">
      <view class="sec">快捷入口</view>
      <view class="entry" @click="go('/pages/workorder/list')">工单列表 ›</view>
      <view v-if="isService" class="entry" @click="go('/pages/checkin/checkin')">签到打卡 ›</view>
      <view class="entry" @click="go('/pages/mine/mine')">我的 ›</view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { request } from "../../api";
import { auth } from "../../stores/auth";

const signedIn = ref(false);
const todoCount = ref(0);

// 按角色裁剪：服务人员显示签到，客户侧显示「我的报障」视角
const roleCodes = computed(() => (auth.user?.roles || []).map((r: any) => r.code));
const isService = computed(() => roleCodes.value.some((c: string) => ["sec_staff", "cs_staff"].includes(c)));
const isCustomer = computed(() => roleCodes.value.some((c: string) => ["cust_admin", "cust_service"].includes(c)));

async function load() {
  if (!auth.user) await auth.fetchMe().catch(() => {});
  try {
    const today = await request<any>({ url: "/api/v1/checkins/today" });
    signedIn.value = (today.records || []).some((r: any) => r.check_type === "签到");
  } catch (e) {}
  try {
    const wo = await request<any>({ url: "/api/v1/work-orders?page=1&size=1" });
    todoCount.value = wo.total || 0;
  } catch (e) {}
}

onShow(load);

function go(url: string) {
  uni.navigateTo({ url });
}
</script>

<style>
.wrap { padding: 24rpx; }
.card { background: #fff; border-radius: 16rpx; padding: 32rpx; margin-bottom: 24rpx; }
.hello { font-size: 38rpx; font-weight: 700; }
.sub { color: #8c959f; margin-top: 8rpx; }
.grid { display: flex; gap: 24rpx; margin-bottom: 24rpx; }
.cell { flex: 1; background: #fff; border-radius: 16rpx; padding: 40rpx 0; text-align: center; }
.num { font-size: 44rpx; font-weight: 700; color: #0a3d91; }
.label { color: #8c959f; font-size: 26rpx; margin-top: 8rpx; }
.sec { font-weight: 700; margin-bottom: 12rpx; }
.entry { padding: 20rpx 0; border-bottom: 1rpx solid #f0f1f3; color: #333; }
</style>
