/** Local Unsplash-sourced covers for the resource board (interview / teaching scenes). */
export const libraryBoardCovers = {
  'ntce-primary': '/library/covers/cover-official.jpg',
  'ntce-secondary': '/library/covers/cover-interview.jpg',
  'ntce-kindergarten': '/library/covers/cover-kindergarten.jpg',
  'fraction-knowledge': '/library/covers/cover-fraction.jpg',
  'fraction-misconceptions': '/library/covers/cover-misconception.jpg',
  'fraction-micro-lesson': '/library/covers/cover-lesson.jpg',
  'presentation-checklist': '/library/covers/cover-checklist.jpg',
  'review-six-dimensions': '/library/covers/cover-rubric.jpg',
  'review-evidence-threshold': '/library/covers/cover-evidence.jpg',
  'puer-case': '/library/covers/cover-case.jpg',
  'tangshan-assessment': '/library/covers/cover-assessment.jpg',
  'external-links': '/library/covers/cover-links.jpg',
}

export function boardCoverFor(item) {
  if (!item) return ''
  return item.boardImage || libraryBoardCovers[item.id] || item.thumbnail || ''
}
