<template>
  <view class="wrap">
    <view class="card">
      <view class="row"><text class="lbl">工单号</text><text>{{ wo.no }}</text></view>
      <view class="row"><text class="lbl">状态</text><text class="status">{{ wo.status }}</text></view>
      <view class="row"><text class="lbl">类型</text><text>{{ wo.type }}</text></view>
      <view class="row"><text class="lbl">优先级</text><text>{{ wo.priority }}</text></view>
      <view class="row"><text class="lbl">项目</text><text>{{ wo.project || "—" }}</text></view>
      <view class="row"><text class="lbl">SLA 时限</text><text>{{ wo.sla_deadline || "—" }}</text></view>
      <view class="row"><text class="lbl">进度</text><text>{{ wo.progress }}%</text></view>
    </view>
    <view class="card">
      <view class="sec">描述</view>
      <text>{{ wo.description || "—" }}</text>
    </view>
    <view class="hint">状态流转请在 PC 端工单管理完成（工作流引擎校验）。</view>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { request } from "../../api";

const wo = ref<any>({});

onLoad(async (options: any) => {
  const id = options?.id;
  if (!id) return;
  try {
    wo.value = await request<any>({ url: `/api/v1/work-orders/${id}` });
  } catch (e) {}
});
</script>

<style>
.wrap { padding: 24rpx; }
.card { background: #fff; border-radius: 16rpx; padding: 28rpx; margin-bottom: 20rpx; }
.row { display: flex; justify-content: space-between; padding: 12rpx 0; border-bottom: 1rpx solid #f5f6f8; font-size: 28rpx; }
.lbl { color: #8c959f; }
.status { color: #0a3d91; font-weight: 600; }
.sec { font-weight: 700; margin-bottom: 12rpx; }
.hint { text-align: center; color: #b0b6bd; font-size: 24rpx; padding: 24rpx; }
</style>
