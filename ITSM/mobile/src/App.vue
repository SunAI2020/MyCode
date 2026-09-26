<script setup lang="ts">
import { onLaunch } from "@dcloudio/uni-app";
import { getToken } from "./api";

onLaunch(() => {
  // 已登录则直达工作台，否则停在登录页
  if (getToken()) {
    uni.reLaunch({ url: "/pages/index/index" });
  }
});
</script>

<style>
page {
  background: #f5f7fa;
}
</style>
