<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常；通行证待办按过滤后的有效明细统计。</p>
      </div>
    </header>

    <div v-if="errorMessage" class="error-panel">
      <span class="error-text">运营概览取不到数据：{{ errorMessage }}</span>
      <button class="btn primary" type="button" :disabled="loading" @click="loadOverview">
        {{ loading ? '查询中…' : '重新查一次' }}
      </button>
    </div>

    <template v-else>
      <div class="stat-row">
        <article v-for="card in cards" :key="card.label" class="stat-card">
          <span class="stat-label">{{ card.label }}</span>
          <strong class="stat-value">{{ card.value }}</strong>
        </article>
      </div>
      <table class="data-table">
        <thead>
          <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in moduleRows" :key="row.name">
            <td>{{ displayName(row.name) }}</td>
            <td>{{ row.created }}</td>
            <td>{{ row.pending }}</td>
            <td>{{ row.abnormal }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const loading = ref(false)
const errorMessage = ref('')

// 业务模块英文名到看板中文名的映射，未列出的模块直接显示英文标识。
const MODULE_LABELS: Record<string, string> = {
  flightstand: '机位分配',
  marshalling: '引导入位',
  bridge: '廊桥对接',
  baggage: '行李装卸',
  catering: '航食配餐',
  fueling: '航油加注',
  deicing: '除冰作业',
  lavatory: '清水排污',
  pushback: '推出开车',
  gse: '地面设备',
  cargo: '货物装卸',
  clearance: '放行签派',
  turnaround: '过站保障',
  ramp: '机坪巡查',
  weather2: '航空气象',
  vehicle: '特种车辆',
  staffshift: '人员排班',
  runway: '跑道灯光',
  emergencyplan: '应急处置',
  qualitycheck: '质量监察',
  passbadge: '员工通行证',
}

function displayName(name: string) {
  return MODULE_LABELS[name] ?? name
}

async function loadOverview() {
  loading.value = true
  errorMessage.value = ''
  try {
    const response = await request('/api/overview')
    if (!response.ok) {
      throw new Error(`接口返回 ${response.status}，请稍后重试`)
    }
    const payload = (await response.json()) as Overview
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '请求未送达，请检查后端服务'
  } finally {
    loading.value = false
  }
}

onMounted(loadOverview)
</script>
