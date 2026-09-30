<template>
  <section class="page" data-module="passbadge">
    <header class="page-head">
      <div>
        <h2>员工通行证（机坪门禁）</h2>
        <p class="page-desc">
          先选所属单位或门禁级别定位通行证，结果按有效期临近程度排列；同一员工被多单位重复授权时以最近办理的为准，
          过期或门禁权限与岗位不符的证件先过滤，并在下方逐条说明。
        </p>
      </div>
    </header>

    <div class="stat-row">
      <article class="stat-card">
        <span class="stat-label">当前有效通行证（命中筛选）</span>
        <strong class="stat-value">{{ total }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">{{ renewWindow }} 天内待续办</span>
        <strong class="stat-value">{{ pendingTotal }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">已过滤（不参与筛选）</span>
        <strong class="stat-value">{{ excluded.length }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>所属单位</span>
        <select v-model="unit">
          <option value="">全部单位</option>
          <option v-for="item in units" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>门禁权限级别</span>
        <select v-model="level">
          <option value="">全部级别</option>
          <option v-for="item in levels" :key="item" :value="item">{{ item }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>姓名 / 通行证编号</span>
        <input v-model="keyword" placeholder="输入姓名或通行证编号" />
      </label>
      <button class="btn primary" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="errorMessage" class="error-panel">
      <span class="error-text">{{ errorMessage }}</span>
      <button class="btn" type="button" :disabled="loading" @click="reload">
        {{ loading ? '查询中…' : '重新查一次' }}
      </button>
    </div>

    <template v-else>
      <table class="data-table">
        <thead>
          <tr>
            <th>通行证编号</th>
            <th>姓名</th>
            <th>所属单位</th>
            <th>所在岗位</th>
            <th>门禁级别</th>
            <th>办理日期</th>
            <th>有效期至</th>
            <th>剩余有效期</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id">
            <td>{{ row['通行证编号'] }}</td>
            <td>{{ row['姓名'] }}</td>
            <td>{{ row['所属单位'] }}</td>
            <td>{{ row['所在岗位'] }}</td>
            <td>
              <span :class="{ 'badge-warn': row.days_to_expiry <= renewWindow }">{{ row['门禁级别'] }}</span>
            </td>
            <td>{{ row['办理日期'] }}</td>
            <td>{{ row['有效期至'] }}</td>
            <td>
              <span :class="row.days_to_expiry <= renewWindow ? 'text-warn' : ''">
                {{ row.days_to_expiry }} 天
                <em v-if="row.days_to_expiry <= renewWindow" class="renew-tag">待续办</em>
              </span>
            </td>
            <td class="row-actions">
              <button class="link" type="button" @click="openDetail(row)">查看明细</button>
            </td>
          </tr>
          <tr v-if="!loading && !rows.length">
            <td colspan="9" class="empty-state">当前条件下没有可使用的通行证，可调整单位或级别后再查</td>
          </tr>
          <tr v-if="loading">
            <td colspan="9" class="empty-state">通行证清单查询中…</td>
          </tr>
        </tbody>
      </table>

      <section v-if="excluded.length" class="excluded-box">
        <h3 class="excluded-title">以下 {{ excluded.length }} 条已被过滤，不参与本次筛选：</h3>
        <ul class="excluded-list">
          <li v-for="item in excluded" :key="item.id">
            <span class="excluded-id">{{ item['通行证编号'] }} · {{ item['姓名'] }}（{{ item['所属单位'] }}）</span>
            <span class="excluded-reason">{{ item['排除原因'] }}</span>
          </li>
        </ul>
      </section>
    </template>

    <footer class="page-foot">
      <span>共 {{ total }} 条有效通行证；待续办数按全部有效证统计，不随当前筛选变化</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onActivated, onMounted, ref, watch, nextTick } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'

import { request } from '@/api/client'

defineOptions({ name: 'PassbadgeList' })

type PassRow = {
  id: number
  通行证编号: string
  姓名: string
  所属单位: string
  所在岗位: string
  门禁级别: string
  办理日期: string
  有效期至: string
  days_to_expiry: number
  pending?: boolean
  排除原因?: string
}

type ListPayload = {
  items: PassRow[]
  total: number
  units: string[]
  levels: string[]
  excluded: PassRow[]
  pending_total: number
  renew_window_days?: number
}

const ENDPOINT = '/api/passbadge'
const router = useRouter()

// 单位与级别是两个独立条件：切换单位只重查，绝不重置已选级别。
const unit = ref('')
const level = ref('')
const keyword = ref('')

const units = ref<string[]>([])
const levels = ref<string[]>([])
const rows = ref<PassRow[]>([])
const excluded = ref<PassRow[]>([])
const total = ref(0)
const pendingTotal = ref(0)
const renewWindow = ref(30)
const loading = ref(false)
const errorMessage = ref('')

// keep-alive 缓存本页：进明细前记住滚动位置，返回后恢复到上一次看的位置。
let savedScrollY = 0

async function reload() {
  loading.value = true
  errorMessage.value = ''
  const params = new URLSearchParams()
  if (unit.value) params.set('unit', unit.value)
  if (level.value) params.set('level', level.value)
  if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) {
      let detail = ''
      try {
        detail = (await response.json())?.detail ?? ''
      } catch {
        detail = ''
      }
      throw new Error(detail || `通行证清单读取失败（接口返回 ${response.status}）`)
    }
    const payload = (await response.json()) as ListPayload
    units.value = payload.units ?? []
    levels.value = payload.levels ?? []
    rows.value = payload.items ?? []
    excluded.value = payload.excluded ?? []
    total.value = payload.total ?? rows.value.length
    pendingTotal.value = payload.pending_total ?? 0
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : '通行证清单取不到数据，请检查服务后重试'
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  unit.value = ''
  level.value = ''
  keyword.value = ''
  void reload()
}

function openDetail(row: PassRow) {
  void router.push({ name: 'passbadge-detail', params: { id: row.id } })
}

// 选择单位或级别后立即筛选；两个条件互不干扰。
watch([unit, level], () => {
  void reload()
})

onMounted(reload)
onBeforeRouteLeave(() => {
  savedScrollY = window.scrollY
})
onActivated(() => {
  void nextTick(() => window.scrollTo({ top: savedScrollY }))
})
</script>
