import { parseCourseId } from '../utils/navigation.js';
// Preserve the chosen skill without starting media or changing the supported classroom scenario.
export function classroomEntry(to = {}) {
  const mode = to.query?.mode;
  const query = mode === 'fragment' ? { mode } : {};
  const courseId = Array.isArray(to.query?.courseId) ? null : parseCourseId(to.query?.courseId);
  if (courseId) query.courseId = String(courseId);
  return { path: '/classroom', query };
}
