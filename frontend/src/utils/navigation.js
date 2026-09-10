export function normalizeSearchQuery(value) {
  return String(value ?? '').trim().replace(/\s+/g, ' ')
}

export function parseCourseId(value) {
  const text = String(value ?? '').trim()
  if (!/^\d+$/.test(text)) return null
  const id = Number(text)
  return Number.isSafeInteger(id) && id > 0 ? id : null
}

export function buildSearchLocation(value) {
  const q = normalizeSearchQuery(value)
  return q ? { path: '/courses', query: { q } } : { path: '/courses' }
}

export function filterCourses(courses, query, filter = 'all') {
  const normalizedQuery = normalizeSearchQuery(query).toLocaleLowerCase()
  return (courses || []).filter((course) => {
    const stage = String(course.stage || '')
    const haystack = [course.title, course.category, course.description, stage]
      .map((value) => String(value || '').toLocaleLowerCase())
      .join(' ')
    const matchesFilter = filter === 'all' || stage.includes(filter)
    const matchesQuery = !normalizedQuery || haystack.includes(normalizedQuery)
    return matchesFilter && matchesQuery
  })
}
