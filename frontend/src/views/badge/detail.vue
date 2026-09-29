<template>
  <section class="page" data-module="badge-detail">
    <header class="page-head">
      <div>
        <h2>通行证单张明细</h2>
        <p class="page-desc">核对这张通行证的单位、岗位、门禁权限与有效期；被过滤的旧证/失效证会直接标注原因。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回清单（保留上次条件与位置）</button>
      </div>
    </header>

    <div v-if="errorMessage" class="notice error-notice" role="alert">
      <span>{{ errorMessage }}</span>
      <button class="btn small" type="button" @click="reload">重新查询</button>
    </div>

    <div v-if="loading" class="notice">正在读取通行证明细…</div>

    <article v-else-if="entry" class="detail-card">
      <header class="detail-head">
        <div>
          <h3>{{ entry['姓名'] }} · {{ entry['通行证编号'] }}</h3>
          <p class="page-desc">{{ entry['所属单位'] }} · {{ entry['岗位'] }}</p>
        </div>
        <span v-if="entry['参与筛选']" :class="entry['临期预警'] ? 'tag tag-warn' : 'tag tag-ok'">
          {{ entry['到期提示'] }}
        </span>
        <span v-else class="tag tag-danger">已过滤 · {{ entry['过滤类别'] }}</span>
      </header>

      <table class="data-table detail-table">
        <tbody>
          <tr v-for="field in detailFields" :key="field.label">
            <th>{{ field.label }}</th>
            <td>{{ entry[field.key] ?? '—' }}</td>
          </tr>
        </tbody>
      </table>

      <div v-if="!entry['参与筛选']" class="notice warn-notice">
        <strong>过滤原因：</strong>{{ entry['过滤原因'] }}。该通行证不参与清单筛选，概览待办按对应口径统计。
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

const route = useRoute()
const router = useRouter()

const entry = ref<Row | null>(null)
const loading = ref(false)
const errorMessage = ref('')

const detailFields = [
  { label: '通行证编号', key: '通行证编号' },
  { label: '姓名', key: '姓名' },
  { label: '工号', key: '工号' },
  { label: '所属单位', key: '所属单位' },
  { label: '岗位', key: '岗位' },
  { label: '门禁权限', key: '门禁权限' },
  { label: '有效期起', key: '有效期起' },
  { label: '有效期止', key: '有效期止' },
  { label: '办理时间', key: '办理时间' },
] as const

async function reload() {
  loading.value = true
  errorMessage.value = ''
  entry.value = null
  const id = String(route.params.id)
  try {
    const response = await request(`/api/badge/${id}`)
    if (response.status === 404) {
      throw new Error(`通行证 ${id} 不存在或已注销，请确认编号后让值班员重新查询`)
    }
    if (!response.ok) {
      throw new Error(`通行证明细读取失败（接口返回 ${response.status}），请重新查询一次`)
    }
    entry.value = (await response.json()) as Row
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '通行证数据取不到，请让值班员重新查询'
  } finally {
    loading.value = false
  }
}

function goBack() {
  // 清单的筛选条件、页码、滚动位置都留在 badgeStore 里，直接回退即可定位原处。
  void router.push('/badge')
}

onMounted(reload)
</script>
