<template>
  <view class="wrap">
    <view class="card">
      <view class="row">
        <text class="lbl">类型</text>
        <view class="seg">
          <view :class="['seg-i', { active: type === '签到' }]" @click="type = '签到'">签到</view>
          <view :class="['seg-i', { active: type === '签退' }]" @click="type = '签退'">签退</view>
        </view>
      </view>
      <view class="row">
        <text class="lbl">位置</text>
        <text class="loc">{{ address || (loc ? `${loc.latitude}, ${loc.longitude}` : "未定位") }}</text>
        <button size="mini" class="mini" @click="getLoc">定位</button>
      </view>
    </view>

    <view class="card" @click="takePhoto">
      <image v-if="photo" :src="photo" class="photo" mode="aspectFill" />
      <view v-else class="ph">📷 拍照留证</view>
    </view>

    <input v-model="remark" placeholder="备注（可选）" class="ipt" />
    <button class="btn" :loading="submitting" @click="submit">{{ type }}</button>
  </view>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { request, uploadImage } from "../../api";

const type = ref("签到");
const loc = ref<any>(null);
const address = ref("");
const photo = ref(""); // 本地临时路径
const remark = ref("");
const submitting = ref(false);

function getLoc() {
  uni.getLocation({
    type: "gcj02",
    success: (res: any) => {
      loc.value = res;
      uni.showToast({ title: "定位成功", icon: "none" });
    },
    fail: () => {
      uni.showToast({ title: "定位失败（H5 需 HTTPS 授权）", icon: "none" });
    },
  });
}

function takePhoto() {
  uni.chooseImage({
    count: 1,
    sourceType: ["camera", "album"],
    success: (res: any) => {
      photo.value = res.tempFilePaths[0];
    },
  });
}

async function submit() {
  submitting.value = true;
  try {
    let photoUrl = "";
    if (photo.value) {
      const up = await uploadImage(photo.value);
      photoUrl = up.url;
    }
    await request({
      url: "/api/v1/checkins",
      method: "POST",
      data: {
        check_type: type.value,
        longitude: loc.value ? loc.value.longitude : null,
        latitude: loc.value ? loc.value.latitude : null,
        address: address.value || null,
        photo_url: photoUrl || null,
        remark: remark.value || null,
      },
    });
    uni.showToast({ title: `${type.value}成功`, icon: "success" });
    photo.value = "";
    remark.value = "";
  } catch (e) {
    /* 错误提示已由 request 处理 */
  } finally {
    submitting.value = false;
  }
}
</script>

<style>
.wrap { padding: 24rpx; }
.card { background: #fff; border-radius: 16rpx; padding: 28rpx; margin-bottom: 24rpx; }
.row { display: flex; align-items: center; justify-content: space-between; padding: 12rpx 0; }
.lbl { color: #8c959f; }
.loc { flex: 1; margin: 0 16rpx; font-size: 26rpx; color: #555; }
.mini { font-size: 24rpx; }
.seg { display: flex; }
.seg-i { padding: 10rpx 32rpx; background: #f0f1f3; border-radius: 30rpx; margin-left: 16rpx; font-size: 26rpx; }
.seg-i.active { background: #0a3d91; color: #fff; }
.photo { width: 100%; height: 360rpx; border-radius: 12rpx; }
.ph { height: 360rpx; display: flex; align-items: center; justify-content: center; color: #b0b6bd; font-size: 30rpx; }
.ipt { border: 1rpx solid #e1e4e8; border-radius: 12rpx; padding: 24rpx; margin-bottom: 24rpx; background: #fff; }
.btn { background: #0a3d91; color: #fff; border-radius: 12rpx; }
</style>
