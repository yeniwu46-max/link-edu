/** Curated Chinese MOOC links for Course Center (external study only). */

export const featuredMoocs = [
  {
    id: 'icourse-self-improve',
    title: '教师课堂教学技能的自我提升',
    platform: '中国大学MOOC',
    summary: '微格导入、提问、讲解、结束四项技能与片段设计。',
    url: 'https://www.icourse163.org/course/icourse-1002419002',
    tags: ['导入', '提问', '讲解', '结束'],
  },
  {
    id: 'icourse-hrbnu-skills',
    title: '课堂教学技能',
    platform: '中国大学MOOC · 哈尔滨师范大学',
    summary: '十项课堂技能与评价量表，对齐微格专项训练。',
    url: 'https://www.icourse163.org/course/HRBNU-1002929004',
    tags: ['板书', '演示', '强化', '组织', '变化'],
  },
  {
    id: 'smartedu-microteaching',
    title: '微格教学与技能训练',
    platform: '智慧树 · 国家智慧教育',
    summary: '微格专项到综合运用，适合模拟授课前后对照。',
    url: 'https://higher.smartedu.cn/course/671ad61416d8a05eedca49d6',
    tags: ['微格', '综合'],
  },
  {
    id: 'chinaooc-hebnu-practice',
    title: '课堂教学技能实训',
    platform: '学堂在线 · 河北师范大学',
    summary: '导入到结课九项实训要点，线下实操前的理论铺垫。',
    url: 'https://www.chinaooc.com.cn/course/687eb7ea16c43a09c0e58cac',
    tags: ['实训'],
  },
  {
    id: 'chinaooc-math-skills',
    title: '新课程理念下的数学教师教学技能',
    platform: '学银在线 · 大庆师范学院',
    summary: '以数学为例讲十项教学技能，可与分数课题训练对照。',
    url: 'https://www.chinaooc.com.cn/course/67bcfe38225d72705e624bff',
    tags: ['数学', '综合'],
  },
]

const selfImprove = {
  label: '延伸：中国大学MOOC · 教师课堂教学技能的自我提升',
  url: 'https://www.icourse163.org/course/icourse-1002419002',
}

const hrbnuSkills = {
  label: '延伸：中国大学MOOC · 课堂教学技能',
  url: 'https://www.icourse163.org/course/HRBNU-1002929004',
}

const microteaching = {
  label: '延伸：智慧树 · 微格教学与技能训练',
  url: 'https://higher.smartedu.cn/course/671ad61416d8a05eedca49d6',
}

/** Map Course.stage → external MOOC link shown in the detail drawer. */
export const moocByStage = {
  '专项01 · 导入': selfImprove,
  '专项02 · 板书': hrbnuSkills,
  '专项03 · 演示': hrbnuSkills,
  '专项04 · 讲解': selfImprove,
  '专项05 · 提问': selfImprove,
  '专项06 · 强化': hrbnuSkills,
  '专项07 · 结束': selfImprove,
  '专项08 · 组织': hrbnuSkills,
  '专项09 · 变化': hrbnuSkills,
  '综合10 · 模拟授课': microteaching,
  '综合11 · 教资试讲': hrbnuSkills,
}

export function moocForCourse(course) {
  if (!course?.stage) return null
  return moocByStage[course.stage] || null
}
