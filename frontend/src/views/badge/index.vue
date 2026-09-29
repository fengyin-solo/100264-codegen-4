<template>
  <section class="page" data-module="badge">
    <header class="page-head">
      <div>
        <h2>员工通行证</h2>
        <p class="page-desc">
          先选所属单位或门禁权限级别，再定位通行证；同一员工重复授权时以最近办理的为准，
          已过期或权限与岗位不符的记录先过滤并在下方说明。
        </p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="exportRows">导出当前清单</button>
        <button class="btn ghost" type="button" @click="reload">重新查询</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>所属单位</span>
        <select :value="badgeStore.unit" @change="onUnitChange">
          <option value="">全部单位</option>
          <option v-for="unit in badgeStore.facets.units" :key="unit" :value="unit">{{ unit }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>门禁权限级别</span>
        <select :value="badgeStore.level" @change="onLevelChange">
          <option value="">全部权限</option>
          <option v-for="level in badgeStore.facets.levels" :key="level" :value="level">{{ level }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>姓名/通行证编号</span>
        <input v-model="keywordInput" placeholder="输入姓名或编号" />
      </label>
      <button class="btn primary" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="errorMessage" class="notice error-notice" role="alert">
      <span>{{ errorMessage }}</span>
      <button class="btn small" type="button" @click="reload">重新查询</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>到期情况</th>
          <th>查看</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :class="{ warn: row['临期预警'] }">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td>
            <span :class="row['临期预警'] ? 'tag tag-warn' : 'tag'">{{ row['到期提示'] }}</span>
          </td>
          <td>
            <RouterLink class="link" :to="`/badge/${row.id}`" @click="rememberScroll">通行证明细</RouterLink>
          </td>
        </tr>
        <tr v-if="!loading && !rows.length">
          <td :colspan="columns.length + 2" class="empty-state">
            当前条件下没有有效通行证，可更换单位或权限级别后重新查询
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 张有效通行证（按有效期由近到远排列）</span>
      <span class="pager">
        <button class="btn small" type="button" :disabled="badgeStore.page <= 1" @click="goPage(badgeStore.page - 1)">上一页</button>
        第 {{ badgeStore.page }} / {{ totalPages }} 页
        <button class="btn small" type="button" :disabled="badgeStore.page >= totalPages" @click="goPage(badgeStore.page + 1)">下一页</button>
      </span>
    </footer>

    <section v-if="excluded.length" class="excluded-box">
      <h3>已过滤记录（{{ excluded.length }} 条，不参与筛选）</h3>
      <ul class="excluded-list">
        <li v-for="item in excluded" :key="String(item.id)">
          <span :class="excludedTagClass(item['过滤类别'])">{{ item['过滤类别'] }}</span>
          <RouterLink class="link" :to="`/badge/${item.id}`">{{ item['通行证编号'] }}</RouterLink>
          {{ item['姓名'] }}（{{ item['工号'] }}）· {{ item['所属单位'] }} — {{ item['过滤原因'] }}
        </li>
      </ul>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onActivated, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useBadgeStore } from '@/stores/badge'

type Row = Record<string, string | number | boolean | null>
type Stat = { label: string; value: number }
type Facets = { units: string[]; levels: string[] }
type BadgePayload = {
  items: Row[]
  total: number
  page: number
  size: number
  excluded: Row[]
  stats: Stat[]
  facets: Facets
}

const ENDPOINT = '/api/badge'
const PAGE_SIZE = 20
const columns = ['通行证编号', '姓名', '工号', '所属单位', '岗位', '门禁权限', '有效期起', '有效期止']

const badgeStore = useBadgeStore()
const keywordInput = ref(badgeStore.keyword)

const rows = ref<Row[]>([])
const excluded = ref<Row[]>([])
const stats = ref<Stat[]>([])
const total = ref(0)
const loading = ref(false)
const errorMessage = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function onUnitChange(event: Event) {
  // 只改单位，权限级别保留在 store 里不动。
  badgeStore.setUnit((event.target as HTMLSelectElement).value)
  void reload()
}

function onLevelChange(event: Event) {
  // 只改权限级别，单位保留在 store 里不动。
  badgeStore.setLevel((event.target as HTMLSelectElement).value)
  void reload()
}

function resetFilters() {
  badgeStore.setUnit('')
  badgeStore.setLevel('')
  badgeStore.setKeyword('')
  keywordInput.value = ''
  void reload()
}

function goPage(page: number) {
  if (page < 1 || page > totalPages.value) return
  badgeStore.setPage(page)
  void reload()
}

function rememberScroll() {
  badgeStore.saveScroll(window.scrollY)
}

function exportRows() {
  const query = new URLSearchParams()
  if (badgeStore.unit) query.set('unit', badgeStore.unit)
  if (badgeStore.level) query.set('level', badgeStore.level)
  window.open(`${ENDPOINT}/export?${query.toString()}`, '_blank')
}

async function reload() {
  loading.value = true
  errorMessage.value = ''
  badgeStore.keyword = keywordInput.value.trim()
  const query = new URLSearchParams({ page: String(badgeStore.page), size: String(PAGE_SIZE) })
  if (badgeStore.unit) query.set('unit', badgeStore.unit)
  if (badgeStore.level) query.set('level', badgeStore.level)
  if (badgeStore.keyword) query.set('keyword', badgeStore.keyword)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error(`通行证清单读取失败（接口返回 ${response.status}），请让值班员重新查询一次`)
    }
    const payload = (await response.json()) as BadgePayload
    rows.value = payload.items ?? []
    excluded.value = payload.excluded ?? []
    stats.value = payload.stats ?? []
    total.value = payload.total ?? 0
    if (payload.facets) {
      badgeStore.setFacets(payload.facets)
    }
    // 明细可能在别处发生变化，停在超出范围的页码时回到最后一页。
    if (badgeStore.page > totalPages.value) {
      badgeStore.setPage(totalPages.value)
      await reload()
    }
  } catch (error) {
    rows.value = []
    excluded.value = []
    errorMessage.value = error instanceof Error ? error.message : '通行证数据取不到，请重新查询'
  } finally {
    loading.value = false
    // 返回清单时停在上一次浏览的位置。
    requestAnimationFrame(() => window.scrollTo({ top: badgeStore.scrollTop }))
  }
}

function excludedTagClass(category: string | number | boolean | null): string {
  if (category === '重复授权') return 'tag tag-muted'
  return 'tag tag-danger'
}

onMounted(reload)
// 路由切走又切回（组件被 keep-alive）时同样恢复滚动位置。
onActivated(() => {
  requestAnimationFrame(() => window.scrollTo({ top: badgeStore.scrollTop }))
})
</script>
