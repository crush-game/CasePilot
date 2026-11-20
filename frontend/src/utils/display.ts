import type { Priority, TicketStatus } from '../types'

export const statusLabels: Record<TicketStatus, string> = {
  QUEUED: '排队中', RUNNING: '调查中', WAITING_HUMAN: '待人工处理',
  WAITING_CUSTOMER: '等待客户反馈', PENDING_CONFIRMATION: '待确认方案',
  RESOLVED: '已解决', CLOSED_UNRESOLVED: '未解决结案',
}
export const priorityLabels: Record<Priority, string> = { low: '低', normal: '普通', high: '高', urgent: '紧急' }
export const nodeLabels: Record<string, string> = {
  parse_request: '解析问题', supervisor: '判断下一步', knowledge_investigation: '查询知识',
  fault_investigation: '调查故障', generate_solution: '生成方案', validate_solution: '校验方案',
  human_interrupt: '人工补充完成', finalize_run: '调查完成',
  'knowledge.begin': '建立知识子任务', 'knowledge.search': '检索知识资料', 'knowledge.assess': '检查材料与问题',
  'knowledge.rewrite': '改写后补检索', 'knowledge.context': '补取相邻步骤', 'knowledge.finish': '返回知识发现',
  'fault.begin': '建立故障子任务', 'fault.plan': '选择调查动作', 'fault.execute': '查询反馈与日志',
  'fault.analyze': '分析领域证据', 'fault.finish': '返回故障发现',
}
export const reasonLabels: Record<string, string> = {
  MISSING_FACTS: '需要补充信息', TAKEOVER_REQUESTED: '人工请求接管', BUDGET_EXHAUSTED: '本轮调查已达上限',
  MOCK_TOOL_ERROR: '模拟数据查询失败', FRAMEWORK_ERROR: '调查异常，需人工核查',
  GRAPH_VERSION_UNSUPPORTED: '运行版本已变化，需重新调查', CHECKPOINT_MISSING: '恢复记录缺失', PAUSE_MISMATCH: '恢复记录不匹配',
  NO_PROGRESS: '补查没有新进展', KNOWLEDGE_CONFLICT: '知识来源存在冲突', KNOWLEDGE_GAP: '资料尚不足以回答',
  INSUFFICIENT_EVIDENCE: '需要补充支持材料', REMEDIES_EXHAUSTED: '有限补查后仍缺依据',
  KNOWLEDGE_TASK_BUDGET: '本轮知识调查已达上限', PROVIDER_BUDGET_EXHAUSTED: '本轮模型预算已用完',
  TOOL_BUDGET_EXHAUSTED: '本轮资料查询已达上限', FAULT_TOOLS_NOT_READY: '需要进一步故障调查',
  MODEL_REQUESTED_HUMAN: '模型建议人工核查', ACTION_OUTCOME_UNKNOWN: '上次请求结果不明，需人工核查',
  EVIDENCE_NOT_APPLICABLE: '引用资料已变化或不适用', PROVIDER_TIMEOUT: '模型服务超时',
  FEEDBACK_SELECTION_REQUIRED: '存在多条反馈，需要人工选择', FEEDBACK_SCOPE_MISMATCH: '反馈与本次问题范围不匹配',
  NO_FEEDBACK: '未找到客户反馈', NO_MATCHING_RECORD: '未找到匹配设备、版本和时间的记录',
  NO_DETAILED_LOG: '缺少当前领域所需的详细日志', TELEMETRY_ONLY: '仅有WiFi埋点，需要人工补查',
  NO_TELEMETRY: '无详细日志且未找到WiFi埋点', NO_MATCHING_LOG_WINDOW: '查看窗口内没有匹配日志',
  INSUFFICIENT_DOMAIN_EVIDENCE: '当前领域缺少日志证据', EVIDENCE_WINDOW_TRUNCATED: '窗口记录过多，需要人工缩小范围',
  AUTH_FAILED: '日志接口认证失败', TIMEOUT: '日志接口超时', RATE_LIMITED: '日志接口限流',
  DOWNLOAD_FAILED: '日志下载失败', PARSE_FAILED: '日志格式无法解析', UNSAFE_ARCHIVE: '日志压缩包不符合读取要求',
  LOG_LIMIT_EXCEEDED: '日志超过读取上限', ARTIFACT_CORRUPTED: '日志校验和已变化',
  ENTERPRISE_SOURCE_CHANGED: '模拟资料在建单后已变化，请重新调查', UNSUPPORTED_DOMAIN: '当前领域尚不支持',
  FAULT_MODEL_REQUESTED_HUMAN: '故障调查建议人工核查',
}
export function displayTime(value?: string | null): string {
  if (!value) return '未提供'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '时间无效'
  return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', dateStyle: 'short', timeStyle: 'short', hour12: false }).format(date)
}
export function beijingISO(value: string): string | undefined {
  return value ? `${value.length === 16 ? `${value}:00` : value}+08:00` : undefined
}
export function shortTicket(value: string): string { return value.length > 24 ? `${value.slice(0, 21)}…` : value }
