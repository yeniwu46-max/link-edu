import { filterCourses, normalizeSearchQuery } from '../utils/navigation.js'

export const DESK_SKILLS = Object.freeze([
  { id:'专项01', label:'导入', object:'邀请函', points:'59,209 187,181 211,239 85,271', x:13, y:32 },
  { id:'专项02', label:'板书', object:'黑板', points:'202,107 340,83 368,202 220,226', x:27, y:14 },
  { id:'专项03', label:'演示', object:'投影仪', points:'379,142 391,114 465,96 506,113 524,176 419,200', x:44, y:14 },
  { id:'专项04', label:'讲解', object:'书本', points:'596,42 713,63 853,91 819,257 537,194', x:71, y:7 },
  { id:'专项05', label:'提问', object:'提示卡', points:'865,181 965,205 934,290 840,270', x:93, y:31 },
  { id:'专项06', label:'强化', object:'印章', points:'735,256 770,256 774,285 797,303 794,332 760,347 705,321 708,297 737,281', x:76, y:44 },
  { id:'专项07', label:'结束', object:'铃', points:'771,352 794,352 797,375 818,385 820,417 784,440 722,424 722,397 750,375 771,372', x:78, y:76 },
  { id:'专项08', label:'组织', object:'计划夹板', points:'86,286 146,273 154,266 172,272 230,277 263,437 117,459', x:16, y:51 },
  { id:'专项09', label:'变化', object:'彩色纸扇', points:'855,324 882,314 987,353 973,402 905,430 855,414 847,345', x:93, y:59 },
  { id:'综合', label:'综合', object:'教案本', points:'275,250 444,245 617,242 638,290 691,421 651,432 276,440 261,418', x:48, y:44 },
])

export function courseSkill(course) {
  const source = `${course.stage || ''} ${course.category || ''}`
  const exact = DESK_SKILLS.find(skill => source.includes(skill.id))
  return exact?.id || DESK_SKILLS.find(skill => source.includes(skill.label))?.id || null
}

export function deskCourses(courses, query = '') {
  const q = normalizeSearchQuery(query)
  const direct = new Set(filterCourses(courses, q).map(course => course.id))
  const skills = q ? DESK_SKILLS.filter(skill => `${skill.label}${skill.object}`.includes(q)).map(skill => skill.id) : []
  return courses.filter(course => direct.has(course.id) || skills.includes(courseSkill(course)))
}

export function preferredCourse(courses, currentId) {
  return courses.find(course => String(course.id) === String(currentId)) || courses.find(course => course.status === 'in_progress') || courses[0] || null
}
