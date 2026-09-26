<template>
  <view class="wrap">
    <scroll-view scroll-x class="tabs">
      <view
        v-for="s in statuses"
        :key="s"
        class="tab"
        :class="{ active: status === s }"
        @click="setStatus(s)"
      >{{ s }}</view>
    </scroll-view>

    <view v-for="wo in filtered" :key="wo.id" class="card" @click="open(wo.id)">
      <view class="row">
        <text class="no">{{ wo.no }}</text>
        <text class="status">{{ wo.status }}</text>
      </view>
      <view class="title">{{ wo.project || wo.type }}</view>
      <view class="desc">{{ wo.description || "—" }}</view>
    </view>
    <view v-if="!filtered.length" class="empty">暂无工单</view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { request } from "../../api";

const statuses = ["全部", "待派单", "已派单", "进行中", "待验收", "已完成"];
const items = ref<any[]>([]);
const status = ref("全部");

const filtered = computed(() =>
  status.value === "全部" ? items.value : items.value.filter((w) => w.status === status.value)
);

async function load() {
  try {
    const data = await request<any>({ url: "/api/v1/work-orders?page=1&size=100" });
    items.value = data.items || [];
  } catch (e) {}
}

onShow(load);

function setStatus(s: string) {
  status.value = s;
}
function open(id: number) {
  uni.navigateTo({ url: `/pages/workorder/detail?id=${id}` });
}
</script>

<style>
.wrap { padding: 24rpx; }
.tabs { white-space: nowrap; margin-bottom: 24rpx; }
.tab { display: inline-block; padding: 12rpx 28rpx; margin-right: 16rpx; background: #fff; border-radius: 30rpx; color: #666; font-size: 26rpx; }
.tab.active { background: #0a3d91; color: #fff; }
.card { background: #fff; border-radius: 16rpx; padding: 28rpx; margin-bottom: 20rpx; }
.row { display: flex; justify-content: space-between; }
.no { font-weight: 700; color: #0a3d91; }
.status { font-size: 24rpx; color: #8c959f; }
.title { margin-top: 12rpx; font-size: 30rpx; }
.desc { margin-top: 8rpx; color: #8c959f; font-size: 26rpx; }
.empty { text-align: center; color: #b0b6bd; padding: 80rpx 0; }
</style>
