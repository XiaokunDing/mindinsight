<!--
Copyright 2022 Huawei Technologies Co., Ltd.All Rights Reserved.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->
<template>
  <div ref="$wrapper" class="wrapper">
    <svg
      ref="$svg"
      v-if="width > 0 && height > 0"
      :width="width" :height="height" :viewBox="`0 0 ${width} ${height}`"
    >
      <slot name="image" :width="width" :height="height"></slot>
    </svg>
  </div>
</template>

<script>
export default {
  data() {
    return {
      width: 0,
      height: 0,
    };
  },

  mounted: function() {
    const {width, height} = this.$refs.$wrapper.getBoundingClientRect();
    this.width = Math.floor(width);
    this.height = Math.floor(height);
  },
};
</script>

<style scoped>
  .wrapper {
    width: 100%;
    height: 100%;
  }
</style>
