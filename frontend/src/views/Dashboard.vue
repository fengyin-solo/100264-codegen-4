<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。</p>
      </div>
    </header>
    <div v-if="errorMessage" class="notice error-notice" role="alert">
      <span>{{ errorMessage }}</span>
      <button class="btn small" type="button" @click="loadOverview">重新查询</button>
    </div>
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
        <tr v-for="row in moduleRows" :key="row.module ?? row.name">
          <td>
            <RouterLink v-if="row.module === 'badge'" class="link" to="/badge">{{ row.name }}</RouterLink>
            <template v-else>{{ row.name }}</template>
          </td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; module?: string; created: number; pending: number; abnormal: number }[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const errorMessage = ref('')

async function loadOverview() {
  errorMessage.value = ''
  try {
    const response = await request('/api/overview')
    if (!response.ok) {
      throw new Error(`运营概览取不到数据（接口返回 ${response.status}），请让值班员重新查询一次`)
    }
    const payload = (await response.json()) as Overview
    cards.value = payload.cards
    moduleRows.value = payload.modules
  } catch (error) {
    cards.value = []
    moduleRows.value = []
    errorMessage.value = error instanceof Error ? error.message : '运营概览数据取不到，请让值班员重新查询一次'
  }
}

onMounted(loadOverview)
</script>
