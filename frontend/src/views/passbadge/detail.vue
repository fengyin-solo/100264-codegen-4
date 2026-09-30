<template>
  <section class="page" data-module="passbadge-detail">
    <header class="page-head">
      <div>
        <h2>通行证明细</h2>
        <p class="page-desc">查看单张通行证的授权单位、门禁级别与有效期；被过滤的证件会直接标明不可用原因。</p>
      </div>
      <div class="page-actions">
        <button class="btn" type="button" @click="goBack">返回清单</button>
      </div>
    </header>

    <div v-if="errorMessage" class="error-panel detail-error">
      <div>
        <strong class="error-text">通行证明细取不到：</strong>
        <span class="error-text">{{ errorMessage }}</span>
      </div>
      <button class="btn primary" type="button" :disabled="loading" @click="loadDetail">
        {{ loading ? '查询中…' : '重新查一次' }}
      </button>
    </div>

    <div v-else-if="loading" class="detail-card">通行证明细查询中…</div>

    <article v-else-if="detail" class="detail-card">
      <header class="detail-head">
        <h3>{{ detail['姓名'] }} · {{ detail['通行证编号'] }}</h3>
        <span :class="['state-chip', isValid ? 'state-ok' : 'state-bad']">{{ detail['当前状态'] }}</span>
      </header>
      <dl class="detail-grid">
        <template v-for="field in detailFields" :key="field">
          <dt>{{ field }}</dt>
          <dd>{{ detail[field] ?? '—' }}</dd>
        </template>
        <dt>剩余有效期</dt>
        <dd>
          <template v-if="detail.days_to_expiry !== undefined">
            {{ detail.days_to_expiry }} 天
            <em v-if="detail.days_to_expiry <= renewWindow && isValid" class="renew-tag">临近到期，待续办</em>
          </template>
          <template v-else>—</template>
        </dd>
      </dl>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { request } from '@/api/client'

type PassDetail = Record<string, string | number | null> & {
  id: number
  days_to_expiry?: number
  当前状态?: string
}

const route = useRoute()
const router = useRouter()

const detail = ref<PassDetail | null>(null)
const loading = ref(false)
const errorMessage = ref('')
const renewWindow = 30

const detailFields = ['所属单位', '所在岗位', '门禁级别', '办理日期', '有效期至']

const isValid = computed(() => (detail.value?.当前状态 ?? '').startsWith('有效'))

async function loadDetail() {
  loading.value = true
  errorMessage.value = ''
  detail.value = null
  const id = Number(route.params.id)
  try {
    const response = await request(`/api/passbadge/${id}`)
    if (response.status === 404) {
      let note = `通行证 ${id} 不存在或已注销`
      try {
        note = (await response.json())?.detail ?? note
      } catch {
        // 404 没有标准错误体时沿用默认提示
      }
      throw new Error(note)
    }
    if (!response.ok) {
      throw new Error(`接口返回 ${response.status}，请稍后重试`)
    }
    detail.value = (await response.json()) as PassDetail
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : '通行证明细取不到数据，请确认服务是否正常'
  } finally {
    loading.value = false
  }
}

function goBack() {
  // 返回清单页（keep-alive 保留上一次的筛选条件与滚动位置）
  if (window.history.state?.back) {
    router.back()
  } else {
    void router.push({ name: 'passbadge-list' })
  }
}

onMounted(loadDetail)
// 极端情况下在同一路由切换 id 也要重新取数
watch(() => route.params.id, loadDetail)
</script>
