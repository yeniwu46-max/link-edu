// Legacy links reach preparation only. Navigation never creates a classroom or opens devices.
export function classroomEntry(to = {}) {
  const mode = to.query?.mode;
  return { path: '/classroom', query: mode === 'fragment' ? { mode } : {} };
}
