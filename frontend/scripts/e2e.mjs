import assert from 'node:assert/strict'
import { spawn, spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { setTimeout as delay } from 'node:timers/promises'
import { chromium } from 'playwright'

const frontend = fileURLToPath(new URL('..', import.meta.url))
const root = resolve(frontend, '..')
const python = resolve(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
const helper = resolve(root, 'scripts/browser_fixture.py')
const output = resolve(root, 'output/playwright')
const origin = 'http://127.0.0.1:15173'
const environment = { ...process.env, PYTHONIOENCODING: 'utf-8' }
const services = []
const results = []
let browser
let activePage

function fixture(...args) {
  const result = spawnSync(python, [helper, ...args], { cwd: root, encoding: 'utf8', env: environment, windowsHide: true, timeout: 45000 })
  if (result.status !== 0) {
    // 仅报告进程状态和异常类型，避免把子进程配置或测试登录信息写入报告。
    const errors = [...(result.stderr ?? '').matchAll(/^([\w.]+(?:Error|Exception)):/gm)]
    const cause = result.error?.code || errors.at(-1)?.[1] || result.signal || 'unknown'
    throw new Error(`测试夹具失败（${args[0]}，退出状态 ${result.status}，${cause}）`)
  }
  return JSON.parse(result.stdout)
}

function service(command, args, env) {
  const child = spawn(command, args, { cwd: frontend, env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] })
  child.stdout.on('data', () => {})
  child.stderr.on('data', () => {})
  services.push(child)
  return child
}

async function ready(url, child) {
  for (let count = 0; count < 150; count++) {
    if (child.exitCode !== null) throw new Error('测试服务启动失败，检查 15173/18003 端口占用。')
    try { if ((await fetch(url)).ok) return } catch {}
    await delay(200)
  }
  throw new Error('测试服务启动超时。')
}

async function scenario(name, run) {
  const started = Date.now()
  await run()
  results.push({ name, passed: true, duration_ms: Date.now() - started })
  console.log(`通过：${name}`)
}

async function login(page, user, target = '/tickets') {
  await page.goto(`${origin}/login`)
  await page.getByLabel('账号', { exact: true }).fill(user.login)
  await page.getByLabel('密码', { exact: true }).fill(user.password)
  await page.getByRole('button', { name: '登录工作台' }).click()
  await page.waitForURL(url => url.pathname === target)
}

async function visible(locator) { await locator.waitFor({ state: 'visible', timeout: 15000 }) }
async function waitStatus(page, status) {
  await visible(page.locator('.detail-heading .status-tag').filter({ hasText: status }))
}
async function post(page, path, body) {
  return page.evaluate(async ({ path, body }) => {
    const response = await fetch(`/api/v1${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': sessionStorage.getItem('casepilot.csrf') || '' }, body: JSON.stringify(body) })
    return { status: response.status, value: await response.json() }
  }, { path, body })
}

try {
  mkdirSync(output, { recursive: true })
  const users = fixture('prepare')
  const api = service(python, [helper, 'api'], environment)
  await ready('http://127.0.0.1:18003/health/ready', api)
  const vite = service(process.execPath, [resolve(frontend, 'node_modules/vite/bin/vite.js'), '--host', '127.0.0.1', '--port', '15173', '--strictPort'], { ...environment, CASEPILOT_API_TARGET: 'http://127.0.0.1:18003' })
  await ready(origin, vite)
  const channel = process.env.CASEPILOT_BROWSER_CHANNEL || (
    existsSync('C:/Program Files/Google/Chrome/Application/chrome.exe') ? 'chrome' :
      existsSync('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe') ? 'msedge' : undefined
  )
  browser = await chromium.launch({ headless: true, ...(channel ? { channel } : {}) })
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'zh-CN', timezoneId: 'Asia/Shanghai' })
  const page = activePage = await context.newPage()
  const pageErrors = []
  const authStatuses = []
  page.on('pageerror', error => pageErrors.push(error.message))
  page.on('response', response => { if (new URL(response.url()).pathname.startsWith('/api/v1/auth/')) authStatuses.push({ path: new URL(response.url()).pathname, status: response.status() }) })
  let created
  let localDraft

  await scenario('登录、错误密码、路由保护与会话刷新', async () => {
    await page.goto(`${origin}/tickets`)
    await page.waitForURL('**/login?**')
    await page.getByLabel('账号', { exact: true }).fill(users.business.login)
    await page.getByLabel('密码', { exact: true }).fill('incorrect-test-password')
    await page.getByRole('button', { name: '登录工作台' }).click()
    await visible(page.getByRole('alert').filter({ hasText: '账号或密码错误' }))
    await page.getByLabel('密码', { exact: true }).fill(users.business.password)
    await page.getByRole('button', { name: '登录工作台' }).click()
    await page.waitForURL(url => url.pathname === '/tickets')
    const before = { hasCsrf: await page.evaluate(() => Boolean(sessionStorage.getItem('casepilot.csrf'))), hasCookie: (await context.cookies()).some(cookie => cookie.name === 'casepilot_session') }
    await page.reload()
    try { await visible(page.getByRole('heading', { name: '工单队列' })) }
    catch (error) { console.log(JSON.stringify({ before, url: page.url(), hasCsrf: await page.evaluate(() => Boolean(sessionStorage.getItem('casepilot.csrf'))), authStatuses, pageErrors })); throw error }
  })

  await scenario('列表分页、筛选与离开页面停止轮询', async () => {
    await visible(page.getByRole('button', { name: '下一页' }))
    await page.getByRole('button', { name: '下一页' }).click()
    await visible(page.getByRole('button', { name: '上一页', exact: true }))
    await page.getByRole('button', { name: '上一页', exact: true }).click()
    await page.getByLabel('工单状态', { exact: true }).selectOption('QUEUED')
    await delay(300)
    assert(await page.locator('.data-table tbody .status-tag').count() > 0)
    await page.getByLabel('工单状态', { exact: true }).selectOption('')
    await page.screenshot({ path: resolve(output, 'workbench-list.png'), fullPage: true })
    await page.getByRole('link', { name: '新建工单', exact: true }).first().click()
    await page.waitForURL(url => url.pathname === '/tickets/new')
    let requests = 0
    const count = request => { if (new URL(request.url()).pathname === '/api/v1/tickets' && request.method() === 'GET') requests++ }
    page.on('request', count)
    await delay(2300)
    page.off('request', count)
    assert.equal(requests, 0)
  })

  await scenario('表单校验、重复提交保护与幂等建单', async () => {
    await page.getByRole('button', { name: '创建工单' }).click()
    await visible(page.getByText('请填写客户遇到的问题。', { exact: true }))
    const title = `P03 浏览器闭环 ${crypto.randomUUID().slice(0, 8)}`
    await page.getByLabel('问题描述').fill(title)
    await page.getByLabel('客户邮箱').fill('browser@example.test')
    let count = 0
    const track = request => { if (new URL(request.url()).pathname === '/api/v1/tickets' && request.method() === 'POST') count++ }
    page.on('request', track)
    const accepted = page.waitForResponse(response => new URL(response.url()).pathname === '/api/v1/tickets' && response.request().method() === 'POST')
    await page.locator('form.create-form').evaluate(form => { form.requestSubmit(); form.requestSubmit() })
    const response = await accepted
    assert.equal(response.status(), 202)
    created = await response.json()
    await page.waitForURL(`**/tickets/${created.ticket_id}`)
    page.off('request', track)
    assert.equal(count, 1)
    fixture('worker', '--run-id', created.run_id)
    await waitStatus(page, '待人工处理')
  })

  await scenario('人工池、认领、离线保留补充草稿', async () => {
    await page.getByRole('link', { name: '人工待办', exact: true }).click()
    await visible(page.getByRole('heading', { name: '人工待办' }))
    await page.goto(`${origin}/tickets/${created.ticket_id}`)
    await page.getByRole('button', { name: '认领待办' }).click()
    await visible(page.getByText('我已认领', { exact: true }))
    await page.getByLabel('补充设备标识').fill('DEMO-P03')
    await page.getByLabel('补充发生时间（北京时间）').fill('2026-11-19T10:30')
    await context.setOffline(true)
    await visible(page.getByText(/网络已断开/))
    assert(await page.getByRole('button', { name: '补充并恢复' }).isDisabled())
    await context.setOffline(false)
    await page.getByText(/网络已断开/).waitFor({ state: 'hidden' })
    assert.equal(await page.getByLabel('补充设备标识').inputValue(), 'DEMO-P03')
  })

  await scenario('人工恢复、断线重连补取事件与来源抽屉', async () => {
    const accepted = page.waitForResponse(response => /\/human-tasks\/[^/]+\/resume$/.test(new URL(response.url()).pathname))
    await page.getByRole('button', { name: '补充并恢复' }).click()
    assert.equal((await accepted).status(), 202)
    await context.setOffline(true)
    fixture('worker', '--run-id', created.run_id)
    await context.setOffline(false)
    await waitStatus(page, '待确认方案')
    await visible(page.getByText('人工补充', { exact: true }).first())
    await visible(page.locator('.timeline strong').filter({ hasText: '调查完成' }))
    await page.getByRole('button', { name: /查看来源说明/ }).click()
    await visible(page.getByText('当前使用固定模拟来源，不包含真实文档原文或客户日志。'))
    await page.keyboard.press('Escape')
  })

  await scenario('409 冲突保留草稿、手动刷新后重试', async () => {
    localDraft = '这是本地保留的回复草稿，请核验设备连接后反馈结果。'
    await page.getByLabel('客户回复草稿').fill(localDraft)
    const current = await (await context.request.get(`${origin}/api/v1/tickets/${created.ticket_id}`)).json()
    const competing = await post(page, `/tickets/${created.ticket_id}/review`, { action_id: crypto.randomUUID(), expected_version: current.version, decision: 'revise', reply_draft: '其他会话已保存的回复' })
    assert.equal(competing.status, 200)
    await page.getByRole('button', { name: '审核通过', exact: true }).click()
    await visible(page.getByRole('alert').filter({ hasText: '工单状态已更新，草稿已保留' }))
    assert.equal(await page.getByLabel('客户回复草稿').inputValue(), localDraft)
    await page.getByRole('button', { name: '刷新状态，保留草稿', exact: true }).first().click()
    await page.getByRole('button', { name: '审核通过', exact: true }).click()
    await visible(page.getByText('方案已审核', { exact: true }))
    await waitStatus(page, '待确认方案')
    await page.evaluate(() => { document.activeElement?.blur(); scrollTo(0, 0) })
    await page.screenshot({ path: resolve(output, 'workbench-detail.png') })
  })

  await scenario('联系记录、明确结案与终态轨迹保留', async () => {
    await page.getByRole('button', { name: '记录已联系客户', exact: true }).click()
    const dialog = page.getByRole('dialog')
    await dialog.getByLabel('联系记录').fill('已在模拟业务渠道联系客户，等待其反馈。')
    await dialog.getByRole('button', { name: '确认提交' }).click()
    await waitStatus(page, '等待客户反馈')
    await page.getByRole('button', { name: '确认结果并结案' }).click()
    await page.getByRole('dialog').getByLabel('结案说明').fill('人工核验模拟问题已经解决。')
    await page.getByLabel('已核验有效的操作（选填）').fill('重新连接后验证设备在线')
    await page.getByRole('button', { name: '确认结案', exact: true }).click()
    await waitStatus(page, '已解决')
    await page.reload()
    await visible(page.getByText('问题已确认解决', { exact: true }))
    await visible(page.locator('.timeline strong').filter({ hasText: '结案结果已记录' }))
    const result = await (await context.request.get(`${origin}/api/v1/tickets/${created.ticket_id}`)).json()
    assert.equal(result.active_run_id, null)
    assert.equal(result.latest_run_id, created.run_id)
  })

  await scenario('P09 明确确认后生成经验候选并审阅归档', async () => {
    assert(fixture('experience', '--ticket-id', created.ticket_id).processed)
    await page.getByRole('link', { name: '查看本工单经验候选' }).click()
    await visible(page.getByRole('heading', { name: '经验候选', exact: true }))
    await visible(page.getByText('重新连接后验证设备在线', { exact: false }))
    await visible(page.getByRole('link', { name: /查看来源工单与证据/ }))
    await page.getByRole('button', { name: '标记已审阅' }).click()
    await page.getByLabel('审阅说明').fill('已复核结案确认与有效操作')
    await page.getByRole('button', { name: '确认提交', exact: true }).click()
    await page.getByLabel('审阅状态').selectOption('reviewed')
    await visible(page.getByText('已复核结案确认与有效操作', { exact: false }))
    await page.getByRole('button', { name: '归档候选' }).click()
    await page.getByLabel('归档说明').fill('验收结束后归档')
    await page.getByRole('button', { name: '确认提交', exact: true }).click()
    await page.getByLabel('审阅状态').selectOption('archived')
    await visible(page.getByText('验收结束后归档', { exact: false }))
  })

  let faultCases
  await scenario('P08 跨领域报告与脱敏日志证据（契约替身）', async () => {
    faultCases = fixture('faults', '--actor-id', users.business.id)
    await page.goto(`${origin}/tickets/${faultCases.cross.ticket_id}`)
    await visible(page.getByRole('heading', { name: '故障调查记录' }))
    await visible(page.getByText('未确认的候选原因', { exact: true }))
    await page.locator('.solution-panel').filter({ has: page.getByRole('heading', { name: '故障调查记录' }) }).getByRole('button', { name: '查看来源说明', exact: false }).click()
    await visible(page.locator('.evidence-item').filter({ hasText: 'disconnect' }))
    assert(!(await page.locator('.el-drawer').innerText()).includes('MOCK_SECRET_P08'))
    assert(await page.locator('.el-drawer__body').evaluate(element => element.scrollWidth <= element.clientWidth + 1), '日志证据抽屉横向溢出')
    await page.screenshot({ path: resolve(output, 'p08-evidence.png'), fullPage: true })
    await page.getByRole('button', { name: 'Close this dialog' }).click()
  })

  await scenario('P08 人工选择反馈并恢复（契约替身）', async () => {
    await page.goto(`${origin}/tickets/${faultCases.multi.ticket_id}`)
    await waitStatus(page, '待人工处理')
    await page.getByRole('button', { name: '认领待办', exact: true }).click()
    const selection = page.getByLabel('选择本次反馈记录')
    await visible(selection)
    assert.equal(await selection.inputValue(), '')
    await page.getByRole('button', { name: '补充并恢复', exact: true }).click()
    await visible(page.getByRole('alert').filter({ hasText: '请选择与本次问题匹配的反馈记录' }))
    await selection.selectOption('feedback:multi:a')
    await page.getByRole('button', { name: '补充并恢复', exact: true }).click()
    await waitStatus(page, '排队中')
    fixture('fault-worker', '--run-id', faultCases.multi.run_id)
    await page.reload()
    await waitStatus(page, '待确认方案')
    await visible(page.getByRole('heading', { name: '故障调查记录' }))
  })

  await scenario('375px 小屏、横屏与减少动画偏好', async () => {
    await page.setViewportSize({ width: 375, height: 812 })
    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.screenshot({ path: resolve(output, 'workbench-mobile.png'), fullPage: true })
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
    await page.setViewportSize({ width: 812, height: 375 })
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
    await page.setViewportSize({ width: 1440, height: 1000 })
  })

  await scenario('会话失效提示与知识角色权限', async () => {
    await context.clearCookies()
    await page.reload()
    await page.waitForURL('**/login?**')
    await visible(page.getByText('登录已过期，请重新登录后继续。'))
    await login(page, users.knowledge)
    await visible(page.getByRole('heading', { name: '当前账号没有工单处理权限' }))
  })
  const consumer = await browser.newContext({ viewport: { width: 375, height: 812 }, locale: 'zh-CN' })
  const support = await consumer.newPage()
  let supportTicket
  await scenario('P11 消费者追问、离线草稿与人工回执幂等', async () => {
    activePage = support
    support.on('pageerror', error => pageErrors.push(error.message))
    await login(support, users.consumer, '/support')
    await visible(support.getByRole('heading', { name: '售后客服' }))
    await consumer.setOffline(true)
    await support.getByLabel('问题', { exact: true }).fill('怎么连接设备？')
    await visible(support.getByText('离线期间输入保留在当前标签页', { exact: false }))
    assert(await support.getByRole('button', { name: '发送', exact: true }).isDisabled())
    await consumer.setOffline(false)
    await support.reload()
    assert.equal(await support.getByLabel('问题', { exact: true }).inputValue(), '怎么连接设备？')
    await support.getByRole('button', { name: '发送', exact: true }).click()
    await support.getByLabel('设备型号', { exact: true }).fill('DEMO-01')
    await support.getByLabel('固件版本', { exact: true }).fill('1.0')
    await support.getByRole('button', { name: '提交设备信息' }).click()
    await visible(support.getByText('来源：模拟设备连接指南'))
    let accepted
    await support.route('**/api/v1/support/turns', async route => {
      const response = await route.fetch()
      assert.equal(response.status(), 201)
      accepted = await response.json()
      await route.abort()
    }, { times: 1 })
    await support.getByRole('button', { name: '转人工', exact: true }).click()
    await visible(support.getByText('提交结果待确认。重试沿用原请求。', { exact: true }))
    assert(accepted.ticket_no.startsWith('CP-'))
    await support.reload()
    await support.getByRole('button', { name: '重试提交' }).click()
    await visible(support.getByRole('status').filter({ hasText: accepted.ticket_no }))
    assert.equal(await support.getByText('已转人工。可在本会话查看工单进度。', { exact: true }).count(), 1)
    assert(await support.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
    supportTicket = accepted.ticket_no
  })
  await scenario('P12 人工回复排队后送达 App', async () => {
    const business = await browser.newContext({ locale: 'zh-CN' })
    const operator = activePage = await business.newPage()
    operator.on('pageerror', error => pageErrors.push(error.message))
    await login(operator, users.business)
    const ticket = fixture('support-ticket', '--ticket-no', supportTicket)
    await operator.goto(`${origin}/tickets/${ticket.ticket_id}`)
    await operator.getByRole('button', { name: '认领待办', exact: true }).click()
    const reply = '请补充故障发生时间。'
    await operator.getByLabel('给消费者的回复').fill(reply)
    const queued = operator.waitForResponse(response => response.url().endsWith('/support-replies') && response.request().method() === 'POST')
    await operator.getByRole('button', { name: '将回复加入发送队列' }).click()
    const response = await queued
    assert.equal(response.status(), 202)
    const delivery = await response.json()
    await visible(operator.getByText('等待发送', { exact: false }))
    assert.equal(await support.getByText(reply, { exact: true }).count(), 0)
    assert(fixture('delivery', '--delivery-id', delivery.id).processed)
    await visible(operator.getByText('已送达', { exact: false }))
    await support.reload()
    await visible(support.getByText(reply, { exact: true }))
    activePage = page
    await business.close()
    await consumer.close()
  })
  await scenario('P15 反馈预览、确认建单和回复原会话', async () => {
    const customerContext = await browser.newContext({ locale: 'zh-CN' })
    const businessContext = await browser.newContext({ locale: 'zh-CN' })
    const customer = activePage = await customerContext.newPage()
    const operator = await businessContext.newPage()
    customer.on('pageerror', error => pageErrors.push(error.message))
    operator.on('pageerror', error => pageErrors.push(error.message))
    try {
      await login(customer, users.consumer, '/support')
      await customer.getByLabel('问题', { exact: true }).fill('升级后 Wi-Fi 反复断开')
      await customer.getByRole('button', { name: '发送', exact: true }).click()
      await visible(customer.getByRole('heading', { name: '确认后转人工' }))
      assert.equal(await customer.getByLabel('确认的问题描述').inputValue(), '升级后 Wi-Fi 反复断开')
      assert.equal(await customer.getByRole('status').filter({ hasText: 'CP-' }).count(), 0)
      await customer.getByLabel('设备型号', { exact: true }).fill('DEMO-01')
      await customer.reload()
      await visible(customer.getByRole('heading', { name: '确认后转人工' }))
      assert.equal(await customer.getByLabel('设备型号', { exact: true }).inputValue(), 'DEMO-01')
      const submit = customer.waitForResponse(response => response.url().endsWith('/support/turns') && response.status() === 201)
      await customer.getByRole('button', { name: '确认转人工', exact: true }).click()
      const { ticket_no: ticketNo } = await (await submit).json()
      await visible(customer.getByRole('status').filter({ hasText: ticketNo }))
      await login(operator, users.business)
      const ticket = fixture('support-ticket', '--ticket-no', ticketNo)
      await operator.goto(`${origin}/tickets/${ticket.ticket_id}`)
      await operator.getByRole('button', { name: '认领待办', exact: true }).click()
      const reply = '请确认断连发生的大致时间。'
      await operator.getByLabel('给消费者的回复').fill(reply)
      const sending = operator.waitForResponse(response => response.url().endsWith('/support-replies') && response.status() === 202)
      await operator.getByRole('button', { name: '将回复加入发送队列' }).click()
      const delivery = await (await sending).json()
      assert.equal(await customer.getByText(reply, { exact: true }).count(), 0)
      assert(fixture('delivery', '--delivery-id', delivery.id).processed)
      await customer.reload()
      await visible(customer.getByText(reply, { exact: true }))
    } finally {
      activePage = page
      await customerContext.close()
      await businessContext.close()
    }
  })
  await scenario('P13 发布后按范围找回历史案例并验证撤回', async () => {
    const business = await browser.newContext({ locale: 'zh-CN' })
    const operator = activePage = await business.newPage()
    operator.on('pageerror', error => pageErrors.push(error.message))
    await login(operator, users.business)
    const scope = { product_ref: `P13-${crypto.randomUUID()}`, firmware_version: '1.0' }
    const makeTicket = () => operator.evaluate(async value => {
      const response = await fetch('/api/v1/tickets', { method: 'POST', headers: {
        'Content-Type': 'application/json', 'Idempotency-Key': crypto.randomUUID(),
        'X-CSRF-Token': sessionStorage.getItem('casepilot.csrf') || '',
      }, body: JSON.stringify(value) })
      if (response.status !== 202) throw new Error('演示工单未创建')
      return response.json()
    }, { ...scope, customer_email: 'experience@example.test', feedback_text: '设备连接反复断开' })
    const source = await makeTicket()
    const close = await post(operator, `/tickets/${source.ticket_id}/close`, {
      action_id: crypto.randomUUID(), expected_version: source.version, outcome: 'resolved',
      reason: '已复核连接恢复', verified_steps: '重新配对并复测连接',
    })
    assert.equal(close.status, 200)
    assert(fixture('experience', '--ticket-id', source.ticket_id).processed)
    const listing = await business.request.get(`${origin}/api/v1/experiences?ticket_id=${source.ticket_id}`)
    const [candidate] = (await listing.json()).items
    assert.equal((await post(operator, `/experiences/${candidate.id}/review`, {
      action_id: crypto.randomUUID(), expected_version: candidate.version, decision: 'review', reason: '复核来源',
    })).status, 200)
    const path = `/experiences/${candidate.id}/publications`
    assert.equal((await post(page, path, { action_id: crypto.randomUUID(), reason: '核对适用范围' })).status, 201)
    const ongoing = await makeTicket()
    await operator.goto(`${origin}/tickets/${ongoing.ticket_id}`)
    await operator.getByRole('button', { name: '查找同范围案例' }).click()
    await visible(operator.getByText('重新配对并复测连接', { exact: true }))
    assert.equal((await post(page, `${path}/1/withdraw`, { action_id: crypto.randomUUID(), reason: '结束演示' })).status, 200)
    await operator.getByRole('button', { name: '查找同范围案例' }).click()
    await visible(operator.getByText('当前没有匹配的已发布案例。', { exact: true }))
    activePage = page
    await business.close()
  })
  assert.deepEqual(pageErrors, [], '浏览器出现未捕获脚本错误')
  writeFileSync(resolve(output, 'e2e-report.json'), JSON.stringify({ passed: results.length, results }, null, 2))
  console.log(`浏览器验收通过：${results.length} 个场景。`)
} catch (error) {
  if (activePage) await activePage.screenshot({ path: resolve(output, 'failure.png'), fullPage: true }).catch(() => {})
  writeFileSync(resolve(output, 'e2e-report.json'), JSON.stringify({ passed: results.length, results, failure: error.message }, null, 2))
  throw error
} finally {
  if (browser) await browser.close()
  for (const child of services.reverse()) {
    if (child.exitCode !== null) continue
    if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, stdio: 'ignore' })
    else child.kill('SIGTERM')
  }
}
