import { defineStore } from 'pinia'

/**
 * 通行证清单的浏览状态：
 * - 单位与权限级别是两个互相独立的条件，切换单位不能抹掉已选的权限级别，反之亦然；
 * - 从清单点进单张再返回时，筛选条件、页码与上次滚动位置都要停在原处。
 */
export const useBadgeStore = defineStore('badge', {
  state: () => ({
    unit: '',
    level: '',
    keyword: '',
    page: 1,
    scrollTop: 0,
    facets: { units: [] as string[], levels: [] as string[] },
  }),
  actions: {
    setUnit(unit: string) {
      if (this.unit === unit) return
      this.unit = unit
      // 条件变化后回到第一页，但权限级别保持不动。
      this.page = 1
      this.scrollTop = 0
    },
    setLevel(level: string) {
      if (this.level === level) return
      this.level = level
      this.page = 1
      this.scrollTop = 0
    },
    setKeyword(keyword: string) {
      this.keyword = keyword
      this.page = 1
    },
    setPage(page: number) {
      this.page = page
      this.scrollTop = 0
    },
    setFacets(facets: { units: string[]; levels: string[] }) {
      this.facets = facets
    },
    saveScroll(top: number) {
      this.scrollTop = top
    },
  },
})
