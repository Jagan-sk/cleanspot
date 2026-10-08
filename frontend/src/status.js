export const OPEN_STATUSES = ['Reported', 'Needs review', 'Assigned', 'Reopened']
export const DONE_STATUSES = ['Resolved', 'Confirmed']

export function statusClass(status) {
  return 'st-' + String(status).toLowerCase().replace(/\s+/g, '-')
}

export function matchesFilter(status, filter) {
  if (filter === 'open') return OPEN_STATUSES.includes(status)
  if (filter === 'done') return DONE_STATUSES.includes(status)
  if (filter === 'dupe') return status === 'Duplicate'
  if (filter === 'review') return status === 'Needs review'
  return true
}