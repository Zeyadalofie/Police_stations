'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const roleNames = {
  data_analyst: 'مسؤول قواعد البيانات',
  police_commander: 'قائد الشرطة',
  officer: 'ضابط',
  mayor: 'العمدة',
}
const roleDescriptions = {
  data_analyst: 'إدارة البيانات والحسابات وصلاحيات الفريق',
  police_commander: 'متابعة العمليات والتحقق منها وكتابة استعلامات قراءة',
  officer: 'تسجيل العمليات ومتابعة مهامك وكتابة استعلامات ضمن نطاقك',
  mayor: 'عرض البيانات المعتمدة وكتابة استعلامات عليها فقط',
}
const statusNames = { pending: 'قيد المتابعة', in_progress: 'جارٍ التنفيذ', completed: 'مكتملة' }
const numberFormat = new Intl.NumberFormat('ar-SA')

async function api(path, options = {}) {
  const response = await fetch(API + path, {
    credentials: 'include',
    ...options,
    headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...(options.headers || {}) },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || 'تعذر إكمال الطلب')
  return data
}

function Icon({ name }) {
  const paths = {
    home: <><path d="m3 10 9-7 9 7"/><path d="M5 9v11h14V9M9 20v-6h6v6"/></>,
    file: <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h8"/></>,
    sql: <><path d="m8 17-5-5 5-5M16 7l5 5-5 5M14 4l-4 16"/></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="10" cy="7" r="4"/><path d="M20 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>,
    shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/></>,
    logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    arrow: <><path d="M19 12H5M12 19l-7-7 7-7"/></>,
    check: <><path d="m5 12 4 4L19 6"/></>,
    lock: <><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></>,
  }
  return <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>
}

function Auth({ onLogin, canRegister }) {
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const register = mode === 'register'

  async function submit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const user = await api(`/api/auth/${register ? 'register' : 'login'}`, { method: 'POST', body: JSON.stringify(form) })
      onLogin(user)
    } catch (exception) {
      setError(exception.message)
    } finally {
      setBusy(false)
    }
  }

  return <main className="auth-page">
    <section className="auth-brand-panel">
      <div className="brand-lockup"><div className="brand-mark"><Icon name="shield"/></div><div><b>مِرْصاد</b><span>مركز العمليات والتحليل</span></div></div>
      <div className="auth-story"><span className="kicker"><i/> مساحة عمل موحّدة</span><h1>القرار يبدأ<br/>من الصورة الكاملة.</h1><p>من غرفة العمليات إلى لوحة المؤشرات، كل معلومة في مكانها وكل حساب يرى ما يحتاجه.</p>
        <div className="auth-mini-stats"><div><b>٤</b><span>أدوار متخصصة</span></div><div><b>١</b><span>مصدر موحد للبيانات</span></div></div>
      </div><div className="auth-foot"><span>منصة تحليل العمليات</span><span>نسخة تجريبية</span></div>
    </section>
    <section className="auth-form-panel"><div className="auth-card"><span className="eyebrow">مرحبًا بك</span><h2>{register ? 'أنشئ حساب مسؤول النظام' : 'تسجيل الدخول'}</h2><p className="muted">{register ? 'أنشئ حساب مسؤول قواعد البيانات الأول، ثم أنشئ حسابات الموظفين من صفحة الصلاحيات.' : 'سجّل الدخول للوصول إلى مساحة العمل الخاصة بك.'}</p>
      <form onSubmit={submit} className="auth-form">
        {register && <label>الاسم الكامل<input required minLength="2" autoComplete="name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="اكتب اسمك"/></label>}
        <label>البريد الإلكتروني<input required type="email" autoComplete="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} placeholder="name@example.com" dir="ltr"/></label>
        <label>كلمة المرور<input required minLength="8" type="password" autoComplete={register?'new-password':'current-password'} value={form.password} onChange={e=>setForm({...form,password:e.target.value})} placeholder="٨ أحرف على الأقل" dir="ltr"/></label>
        {error && <div className="inline-error" role="alert">{error}</div>}
        <button className="button button-primary button-wide" disabled={busy}>{busy?'جارٍ الدخول…':register?'إنشاء حساب المسؤول':'دخول إلى مساحة العمل'}<Icon name="arrow"/></button>
      </form>
      {canRegister&&<div className="auth-toggle">{register?'لديك حساب بالفعل؟':'إعداد أول مرة؟'} <button onClick={()=>{setError('');setMode(register?'login':'register')}}>{register?'سجّل الدخول':'إنشاء حساب المسؤول'}</button></div>}{!canRegister&&<div className="auth-toggle">حسابات الموظفين ينشئها مسؤول قواعد البيانات من صفحة الصلاحيات.</div>}
      <div className="auth-privacy"><Icon name="lock"/><span>تُحمى الجلسات وتُطبّق صلاحيات الحساب من الخادم.</span></div>
    </div></section>
  </main>
}

function ChangePassword({ user, onChanged }) {
  const [form, setForm] = useState({current_password:'',new_password:'',confirm_password:''})
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  async function submit(event) {
    event.preventDefault(); setError('')
    if (form.new_password !== form.confirm_password) { setError('كلمتا المرور الجديدتان غير متطابقتين'); return }
    setBusy(true)
    try { await api('/api/account/change-password',{method:'POST',body:JSON.stringify({current_password:form.current_password,new_password:form.new_password})}); onChanged({...user,must_change_password:false}) }
    catch(exception) { setError(exception.message) }
    finally { setBusy(false) }
  }
  return <main className="auth-page"><section className="auth-brand-panel"><div className="brand-lockup"><div className="brand-mark"><Icon name="shield"/></div><div><b>مِرْصاد</b><span>مركز العمليات والتحليل</span></div></div><div className="auth-story"><span className="kicker"><i/> خطوة أمان أولى</span><h1>غيّر كلمة<br/>المرور المؤقتة.</h1><p>اختر كلمة مرور خاصة بك قبل الدخول إلى مساحة عملك.</p></div></section><section className="auth-form-panel"><div className="auth-card"><span className="eyebrow">مرحبًا {user.name}</span><h2>تحديث كلمة المرور</h2><p className="muted">استخدم كلمة مرور جديدة لا تقل عن ١٢ حرفًا.</p><form className="auth-form" onSubmit={submit}><label>كلمة المرور الأولية<input required minLength="8" type="password" autoComplete="current-password" value={form.current_password} onChange={e=>setForm({...form,current_password:e.target.value})}/></label><label>كلمة المرور الجديدة<input required minLength="12" type="password" autoComplete="new-password" value={form.new_password} onChange={e=>setForm({...form,new_password:e.target.value})}/></label><label>تأكيد كلمة المرور الجديدة<input required minLength="12" type="password" autoComplete="new-password" value={form.confirm_password} onChange={e=>setForm({...form,confirm_password:e.target.value})}/></label>{error&&<div className="inline-error" role="alert">{error}</div>}<button className="button button-primary button-wide" disabled={busy}>{busy?'جارٍ الحفظ…':'حفظ كلمة المرور'}<Icon name="arrow"/></button></form></div></section></main>
}

function StatCard({ label, value, note, tone }) {
  return <article className={`stat-card ${tone || ''}`}><div className="stat-label">{label}<span className="stat-dot"/></div><strong>{value ?? '—'}</strong><small>{note}</small></article>
}

function RecordsTable({ records, user, onStatus, onValidate }) {
  const canManage = ['police_commander', 'data_analyst'].includes(user.role)
  if (!records.length) return <div className="empty-state"><div className="empty-mark"><Icon name="file"/></div><b>لا توجد عمليات مسجلة بعد</b><p>ستظهر السجلات هنا بعد إضافتها إلى النظام.</p></div>
  return <div className="table-scroll"><table><thead><tr><th>العملية</th><th>المنطقة</th><th>الأولوية</th><th>الحالة</th>{user.role==='police_commander'&&<th>التحقق</th>}<th>زمن الاستجابة</th><th>وقت التسجيل</th></tr></thead><tbody>{records.map(row=><tr key={row.id}>
    <td><b>{row.title}</b><small>{row.category} · #{row.id}</small></td><td>{row.region}</td><td><span className={`priority priority-${row.priority==='عاجل'?'urgent':row.priority==='مرتفع'?'high':'normal'}`}>{row.priority}</span></td>
    <td>{canManage?<select className="status-select" value={row.status} onChange={e=>onStatus(row.id,e.target.value)}><option>قيد المتابعة</option><option>جارٍ التنفيذ</option><option>مكتملة</option></select>:<span className={`status-pill ${row.status==='مكتملة'?'done':''}`}>{row.status}</span>}</td>{user.role==='police_commander'&&<td><div className="inline-actions"><button className="text-action" onClick={()=>onValidate(row.id,true)}>اعتماد</button><button className="text-action text-danger" onClick={()=>onValidate(row.id,false)}>إرجاع</button></div><small>{row.validation_state==='approved'?'معتمدة':row.validation_state==='needs_correction'?'تحتاج تصحيح':'بانتظار التحقق'}</small></td>}
    <td>{row.response_minutes == null ? '—' : `${numberFormat.format(row.response_minutes)} د`}</td><td>{new Date(row.occurred_at).toLocaleDateString('ar-SA')}</td>
  </tr>)}</tbody></table></div>
}

function LabTaskChart({ result }) {
  if (!result?.columns?.length || !result.rows?.length) return null

  const monthIndex = result.columns.indexOf('month')
  const isChartNumber = value => typeof value === 'number' ? Number.isFinite(value) : typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value))
  const labelIndexes = result.columns.map((_, index) => index).filter(index => {
    if (index === monthIndex) return false
    if (result.columns[index] === 'dist_num') return true
    return result.rows.some(row => row[index] != null && typeof row[index] === 'string' && !isChartNumber(row[index]))
  })
  const metricIndexes = result.columns.map((_, index) => index).filter(index =>
    index !== monthIndex && result.columns[index] !== 'dist_num' && result.rows.some(row => isChartNumber(row[index]))
  )
  if (!metricIndexes.length) return null

  const metricNames = {crime_records:'الجرائم',crash_records:'الحوادث',assigned_crashes:'الحوادث المسندة',observed_injuries:'قيم الإصابات المرصودة',injuries:'مجموع الإصابات',previous:'الشهر السابق',observed:'القيم المرصودة',mean_injuries:'متوسط الإصابات',unmatched:'غير المطابق',total:'الإجمالي',assigned:'المسند'}
  let categories = result.rows.map((row, rowIndex) => {
    const labels = labelIndexes.map(index => String(row[index] ?? '')).filter(Boolean)
    if (monthIndex >= 0) labels.push(String(row[monthIndex] ?? '').slice(5, 7))
    return { label: labels.join(' · ') || `ملخص ${rowIndex + 1}`, values: metricIndexes.map(index => row[index] == null ? null : Number(row[index])) }
  })
  let series = metricIndexes.map(index => ({ name: metricNames[result.columns[index]] || result.columns[index], color: '' }))

  // A single summary row reads better as one bar per measure.
  if (result.rows.length === 1 && metricIndexes.length > 1) {
    categories = metricIndexes.map((index, metricIndex) => ({label:metricNames[result.columns[index]] || result.columns[index],values:[result.rows[0][index] == null ? null : Number(result.rows[0][index])],sourceIndex:metricIndex}))
    series = [{name:'القيمة',color:''}]
  }

  const colors = ['#428f82','#8177ad','#d19a59','#4b8ab2','#c56d68']
  const maxima = series.map((_, seriesIndex) => Math.max(1,...categories.map(category => Number(category.values[seriesIndex]) || 0)))
  return <section className="lab-result-chart" aria-label="رسم بياني لنتائج المهمة">
    <div className="lab-result-chart-heading"><b>رسم نتائج الاستعلام</b><small>مرّر أفقيًا لاستعراض جميع الفئات · كل سلسلة تستخدم مقياسًا مستقلًا</small></div>
    <div className="lab-result-chart-scroll"><div className="lab-result-chart-groups" style={{minWidth:`${Math.max(100,categories.length * 68)}px`}}>
      {categories.map((category,index)=><div className="lab-result-chart-category" key={`${category.label}-${index}`} title={category.label}>
        <div className="lab-result-chart-bars">{category.values.map((value,seriesIndex)=>value==null?<span className="lab-result-chart-empty" key={seriesIndex} title="لا توجد قيمة سابقة"/>:<i key={seriesIndex} style={{height:`${Math.max(3,(Math.max(0,value)/maxima[seriesIndex])*100)}%`,background:colors[seriesIndex%colors.length]}} title={`${series[seriesIndex].name}: ${numberFormat.format(value)}`}/>)}</div>
        <small>{category.label}</small>
      </div>)}
    </div></div>
    <div className="lab-result-chart-legend">{series.map((item,index)=><span key={item.name}><i style={{background:colors[index%colors.length]}}/>{item.name}</span>)}</div>
  </section>
}

function SQLResults({ result }) {
  if (!result) return null
  if (result.queued) return <div className="query-result"><div className="result-top"><div><b>حُفظ الأمر في سجل الانتظار</b><span>سيعاد التحقق من صلاحية الحساب وتنفيذ الأمر عند عودة الاتصال.</span></div><span className="sql-badge">بانتظار الاتصال</span></div></div>
  return <div className="query-result">
    <div className="result-top"><div><b>{result.columns.length?'نتيجة الاستعلام':'اكتمل تنفيذ الأمر'}</b><span>{result.columns.length?`${numberFormat.format(result.affected_rows)} صف`:`${numberFormat.format(result.affected_rows)} صف متأثر`}{result.truncated?' · عُرض أول ٥٠٠ صف':''}</span></div><span className="result-check"><Icon name="check"/> وصل إلى {result.database||'قاعدة البيانات'}</span></div>
    {result.columns.length ? <div className="table-scroll"><table className="sql-table" dir="ltr"><thead><tr>{result.columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{result.rows.map((row,i)=><tr key={i}>{row.map((v,j)=><td key={j}>{v===null?<i>NULL</i>:String(v)}</td>)}</tr>)}</tbody></table>{!result.rows.length&&<div className="no-rows">الاستعلام لم يُرجع صفوفًا.</div>}</div>:<div className="command-complete">تم تنفيذ الأمر بنجاح.</div>}
  </div>
}

function AppShell({ user, onLogout }) {
  const [page, setPage] = useState('overview')
  const [dashboard, setDashboard] = useState(null)
  const [records, setRecords] = useState([])
  const [users, setUsers] = useState([])
  const [roleHistory, setRoleHistory] = useState([])
  const [accountHistory, setAccountHistory] = useState([])
  const [roleCatalog, setRoleCatalog] = useState([])
  const [commandHistory, setCommandHistory] = useState([])
  const [spatialLabs, setSpatialLabs] = useState([])
  const [labTaskResults, setLabTaskResults] = useState({})
  const [labTaskBusy, setLabTaskBusy] = useState(null)
  const [labDashboard, setLabDashboard] = useState(null)
  const [labDashboardBusy, setLabDashboardBusy] = useState(false)
  const [handoverNote, setHandoverNote] = useState('')
  const [sqlConnection, setSqlConnection] = useState(null)
  const [changeRequests, setChangeRequests] = useState([])
  const [dataRequests, setDataRequests] = useState([])
  const [reports, setReports] = useState([])
  const [draftResults, setDraftResults] = useState({})
  const [requestForm, setRequestForm] = useState({title:'',question:'',complexity:'standard'})
  const [reportForm, setReportForm] = useState({title:'توزيع العمليات حسب المنطقة',statement:'SELECT region, COUNT(*) AS total FROM operation_records GROUP BY region ORDER BY total DESC LIMIT 20',label_column:'region',value_column:'total',chart_type:'bar'})
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [sql, setSql] = useState('SELECT id, title, category, region, status\nFROM operation_records\nORDER BY occurred_at DESC\nLIMIT 20;')
  const [sqlResult, setSqlResult] = useState(null)
  const [sqlBusy, setSqlBusy] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState({ title: '', category: '', region: '', priority: 'عادي' })
  const [roleBusy, setRoleBusy] = useState(null)
  const [employeeForm, setEmployeeForm] = useState({name:'',email:'',role:'officer',temporary_password:''})
  const [employeeBusy, setEmployeeBusy] = useState(false)
  const canSql = true
  const canManageUsers = user.role === 'data_analyst'
  const canCreate = ['officer', 'data_analyst'].includes(user.role)
  const nav = useMemo(() => [
    { id: 'overview', label: 'نظرة عامة', icon: 'home' },
    { id: 'operations', label: user.role === 'mayor' ? 'البيانات المعتمدة' : user.role === 'police_commander' ? 'التحقق من البيانات' : 'العمليات', icon: 'file' },
    ...(user.role==='mayor' ? [{id:'data-requests',label:'طلب بيانات',icon:'plus'}] : []),
    ...(user.role==='police_commander' ? [{id:'data-requests',label:'طلبات البيانات',icon:'file'},{id:'reports',label:'مراجعة الرسوم',icon:'shield'}] : []),
    ...(user.role==='officer' ? [{id:'data-requests',label:'الطلبات المسندة',icon:'file'},{id:'reports',label:'رسومي البيانية',icon:'shield'}] : []),
    {id:'lab-tasks',label:'مهام التحليل المكاني',icon:'file'},
    {id:'district-dashboard',label:'لوحة المناطق والتصدير',icon:'shield'},
    ...(canSql ? [{ id: 'sql', label: 'استعلامات SQL', icon: 'sql' }] : []),
    ...(canManageUsers ? [{ id: 'users', label: 'الصلاحيات', icon: 'users' }, {id:'change-requests',label:'طلبات التعديل',icon:'file'}, {id:'data-requests',label:'طلبات البيانات',icon:'file'}, {id:'reports',label:'الرسوم والتقارير',icon:'shield'}, { id: 'command-log', label: 'سجل أوامر SQL', icon: 'sql' }] : []),
  ], [canManageUsers, canSql, user.role])

  const loadData = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [summary, operationRows] = await Promise.all([api('/api/dashboard'), api('/api/operations')])
      setDashboard(summary)
      setRecords(operationRows)
    } catch (exception) { setError(exception.message) }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { loadData() }, [loadData])
  useEffect(() => {
    if (page === 'command-log' && canManageUsers) api('/api/sql-console/commands').then(setCommandHistory).catch(exception=>setError(exception.message))
    if (page === 'change-requests' && canManageUsers) api('/api/admin/change-requests').then(setChangeRequests).catch(exception=>setError(exception.message))
    if (page === 'data-requests' && user.role!=='mayor') api('/api/data-requests').then(setDataRequests).catch(exception=>setError(exception.message))
    if (page === 'data-requests' && user.role==='mayor') api('/api/data-requests').then(setDataRequests).catch(exception=>setError(exception.message))
    if (page === 'reports') api('/api/reports').then(setReports).catch(exception=>setError(exception.message))
    if (page === 'lab-tasks') api('/api/labs/tasks').then(setSpatialLabs).catch(exception=>setError(exception.message))
    if (page === 'district-dashboard') { setLabDashboardBusy(true); api('/api/labs/district-dashboard').then(setLabDashboard).catch(exception=>setError(exception.message)).finally(()=>setLabDashboardBusy(false)) }
    if (page === 'sql') api('/api/sql-console/status').then(setSqlConnection).catch(exception=>setSqlConnection({connected:false}))
  }, [page, canManageUsers, user.role])
  useEffect(() => {
    if (page !== 'users' || !canManageUsers) return
    Promise.all([api('/api/admin/users'),api('/api/admin/role-history'),api('/api/admin/access-model'),api('/api/admin/account-history')]).then(([accounts,history,model,created])=>{setUsers(accounts);setRoleHistory(history);setRoleCatalog(model);setAccountHistory(created)}).catch(exception=>setError(exception.message))
  }, [page, canManageUsers])

  async function createOperation(event) {
    event.preventDefault(); setError(''); setNotice('')
    try {
      await api('/api/operations', { method: 'POST', body: JSON.stringify(createForm) })
      setCreateForm({ title: '', category: '', region: '', priority: 'عادي' }); setCreateOpen(false)
      setNotice('تمت إضافة العملية'); await loadData()
    } catch (exception) { setError(exception.message) }
  }

  async function changeStatus(id, status) {
    setError('')
    try {
      await api(`/api/operations/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) })
      setRecords(current=>current.map(row=>row.id===id?{...row,status}:row)); setNotice('تم تحديث حالة العملية')
    } catch (exception) { setError(exception.message); await loadData() }
  }

  async function createEmployee(event) {
    event.preventDefault(); setEmployeeBusy(true); setError(''); setNotice('')
    try {
      await api('/api/admin/users',{method:'POST',body:JSON.stringify(employeeForm)})
      setUsers(await api('/api/admin/users'))
      setEmployeeForm({name:'',email:'',role:'officer',temporary_password:''})
      setNotice('تم إنشاء الحساب. أعط الموظف كلمة المرور الأولية ليغيّرها عند أول دخول.')
    } catch(exception) { setError(exception.message) }
    finally { setEmployeeBusy(false) }
  }

  async function changeRole(id, role) {
    setRoleBusy(id); setError(''); setNotice('')
    try {
      await api(`/api/admin/users/${id}/role`, { method: 'PUT', body: JSON.stringify({ role }) })
      setUsers(current=>current.map(row=>row.id===id?{...row,role,role_label:roleNames[role],permissions:roleCatalog.find(item=>item.role===role)?.capabilities||[]}:row)); setRoleHistory(await api('/api/admin/role-history')); setNotice('تم تحديث صلاحية الحساب')
    } catch (exception) { setError(exception.message); await api('/api/admin/users').then(setUsers).catch(()=>{}) }
    finally { setRoleBusy(null) }
  }

  async function validateRecord(id, approved) {
    const note = window.prompt(approved ? 'ملاحظة الاعتماد (اختياري)' : 'سبب الإرجاع للتصحيح') || ''
    try { await api(`/api/operations/${id}/validation`, {method:'POST',body:JSON.stringify({approved,note})}); setNotice(approved?'تم اعتماد السجل':'أُعيد السجل للتصحيح'); await loadData() } catch(exception) { setError(exception.message) }
  }

  async function reviewChange(id, approved) {
    const note = window.prompt(approved?'ملاحظة الاعتماد (اختياري)':'سبب رفض التعديل') || ''
    try { await api(`/api/admin/change-requests/${id}`,{method:'PUT',body:JSON.stringify({approved,note})}); setChangeRequests(rows=>rows.filter(row=>row.id!==id)); setNotice(approved?'تم اعتماد التعديل':'تم رفض التعديل') } catch(exception) { setError(exception.message) }
  }

  async function submitRequestResult(event, id) {
    event.preventDefault(); const result_text=draftResults[id]||''
    try { await api(`/api/data-requests/${id}/submit`,{method:'POST',body:JSON.stringify({result_text})}); setDataRequests(rows=>rows.filter(row=>row.id!==id)); setNotice('أُرسل الرد إلى قائد الشرطة للمراجعة') } catch(exception) { setError(exception.message) }
  }

  async function routeRequest(id, target_role) {
    try { await api(`/api/data-requests/${id}/route`,{method:'PUT',body:JSON.stringify({target_role,note:''})}); setDataRequests(await api('/api/data-requests')); setNotice(target_role==='officer'?'أُسند الطلب إلى الضابط':'أُرسل الطلب إلى مسؤول قواعد البيانات') } catch(exception) { setError(exception.message) }
  }

  async function escalateRequest(id) {
    try { await api(`/api/data-requests/${id}/escalate`,{method:'POST',body:JSON.stringify({target_role:'data_analyst',note:'يتطلب صلاحية أوسع'})}); setDataRequests(rows=>rows.filter(row=>row.id!==id)); setNotice('تم تصعيد الطلب إلى مسؤول قواعد البيانات') } catch(exception) { setError(exception.message) }
  }

  async function reviewRequest(id, approved) {
    const note=window.prompt(approved?'ملاحظة الاعتماد (اختياري)':'سبب رفض الطلب')||''
    try { await api(`/api/data-requests/${id}/review`,{method:'PUT',body:JSON.stringify({approved,note})}); setDataRequests(rows=>rows.filter(row=>row.id!==id)); setNotice(approved?'اعتمد القائد النتيجة وأصبحت متاحة للعمدة':'تم رفض النتيجة') } catch(exception) { setError(exception.message) }
  }

  async function createMayorRequest(event) {
    event.preventDefault()
    try { await api('/api/data-requests',{method:'POST',body:JSON.stringify(requestForm)}); setRequestForm({title:'',question:'',complexity:'standard'}); setNotice('تم إرسال الطلب إلى قائد الشرطة'); setDataRequests(await api('/api/data-requests')) } catch(exception) { setError(exception.message) }
  }

  async function reviewReport(id, approved) {
    const note=window.prompt(approved?'ملاحظة الاعتماد (اختياري)':'سبب رفض الرسم')||''
    try { await api(`/api/reports/${id}/review`,{method:'PUT',body:JSON.stringify({approved,note})}); setReports(rows=>rows.filter(row=>row.id!==id)); setNotice(approved?'تم اعتماد الرسم':'تم رفض الرسم') } catch(exception) { setError(exception.message) }
  }

  async function createReport(event) {
    event.preventDefault()
    try { const report=await api('/api/reports',{method:'POST',body:JSON.stringify(reportForm)}); setReports(rows=>[report,...rows]); setNotice('أُرسل الرسم إلى قائد الشرطة للمراجعة') } catch(exception) { setError(exception.message) }
  }

  async function runLabTask(taskId) {
    setLabTaskBusy(taskId); setError(''); setNotice('')
    try {
      const result=await api('/api/labs/tasks/run',{method:'POST',body:JSON.stringify({task_id:taskId})})
      setLabTaskResults(current=>({...current,[taskId]:result}));
      setNotice(`تم تنفيذ المهمة على ${result.result.database} وأعادت ${numberFormat.format(result.result.affected_rows)} صفًا`)
    } catch(exception) { setError(exception.message) }
    finally { setLabTaskBusy(null) }
  }

  function downloadText(filename, content, mimeType) {
    const url=URL.createObjectURL(new Blob([content],{type:mimeType}))
    const link=document.createElement('a'); link.href=url; link.download=filename; link.click(); URL.revokeObjectURL(url)
  }

  function downloadMonthlyCsv() {
    if (!labDashboard?.monthly?.length) return
    const rows=[['month','crimes','crashes'],...labDashboard.monthly.map(row=>[row.month,row.crimes,row.crashes])]
    downloadText('district_month_summary_2025.csv','\uFEFF'+rows.map(row=>row.join(',')).join('\r\n'),'text/csv;charset=utf-8')
  }

  function downloadProvenance() {
    if (!labDashboard) return
    const handover={presentation_notes:handoverNote.trim(),created_by:name,database:labDashboard.database,generated_at:labDashboard.generated_at}
    downloadText('report_provenance.json',JSON.stringify({...labDashboard.provenance,handover},null,2),'application/json;charset=utf-8')
  }

  async function runSQL(event) {
    event.preventDefault(); setSqlBusy(true); setSqlResult(null); setError(''); setNotice('')
    try { const result = await api('/api/sql-console/execute', { method: 'POST', body: JSON.stringify({ command_id: crypto.randomUUID(), statement: sql }) }); setSqlResult(result); if (result.queued) { setNotice(result.message); api('/api/sql-console/commands').then(setCommandHistory).catch(()=>{}) } }
    catch (exception) { setError(exception.message) }
    finally { setSqlBusy(false) }
  }

  const pageTitle = page==='overview' ? roleNames[user.role] : nav.find(item=>item.id===page)?.label || roleNames[user.role]
  const name = user.name || user.email.split('@')[0]

  return <div className="workspace">
    <aside className="sidebar">
      <div className="brand-lockup side-brand"><div className="brand-mark"><Icon name="shield"/></div><div><b>مِرْصاد</b><span>مركز العمليات والتحليل</span></div></div>
      <div className="side-caption">مساحة العمل</div>
      <nav className="side-nav">{nav.map(item=><button key={item.id} className={`nav-link ${page===item.id?'active':''}`} onClick={()=>{setPage(item.id);setError('');setNotice('')}}><Icon name={item.icon}/><span>{item.label}</span>{item.id==='users'&&<i className="nav-admin-dot"/>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="security-note"><Icon name="lock"/><div><b>صلاحيات محمية</b><span>يتحكم الخادم بما يستطيع كل دور الوصول إليه.</span></div></div>
        <div className="user-chip"><div className="avatar">{name.slice(0,1).toUpperCase()}</div><div className="user-copy"><b>{name}</b><span>{roleNames[user.role]}</span></div><button className="logout-button" onClick={onLogout} title="تسجيل الخروج" aria-label="تسجيل الخروج"><Icon name="logout"/></button></div>
      </div>
    </aside>
    <main className="main-area">
      <header className="topbar"><div className="breadcrumbs"><span>مرصاد</span><b>/</b><strong>{pageTitle}</strong></div><div className="topbar-right"><span className="online-mark"><i/> مساحة آمنة</span><span className="top-date">{new Date().toLocaleDateString('ar-SA',{weekday:'long',day:'numeric',month:'long'})}</span></div></header>
      <div className="page-content">
        {(error||notice)&&<div className={`toast ${error?'toast-error':'toast-success'}`} role="status"><span>{error||notice}</span><button onClick={()=>{setError('');setNotice('')}}>×</button></div>}
        <div className="page-heading"><div><span className="eyebrow">{roleNames[user.role]}</span><h1>{page==='overview'?`أهلًا، ${name}`:pageTitle}</h1><p>{page==='overview'?roleDescriptions[user.role]:page==='sql'?'اكتب استعلامك، وستُطبق قاعدة البيانات حدود صلاحيتك.':page==='users'?'راجع كل حساب وما يقدر عليه وغيّر دوره من صفحة الصلاحيات.':page==='command-log'?'تابع الأوامر التي نُفذت أو تنتظر عودة اتصال Neon.':'تابع السجلات وفق صلاحية حسابك.'}</p></div>
          {page==='operations'&&canCreate&&<button className="button button-primary" onClick={()=>setCreateOpen(value=>!value)}><Icon name="plus"/>{createOpen?'إغلاق النموذج':'تسجيل عملية'}</button>}
        </div>
        {page==='overview'&&<>
          {user.role==='data_analyst'&&<div className="welcome-banner"><div><span className="banner-kicker">مسؤول النظام</span><b>أنت تدير أدوار الفريق</b><p>تعيين الأدوار متاح لك وحدك. مستخدمو SQL يعملون ضمن صلاحيات قاعدة بيانات منفصلة.</p></div><button className="button button-light" onClick={()=>setPage('users')}><Icon name="users"/>إدارة الحسابات</button></div>}
          <section className="stats-grid">
            <StatCard label="إجمالي العمليات" value={numberFormat.format(dashboard?.total||0)} note="ضمن نطاق حسابك" tone="stat-blue"/>
            <StatCard label="قيد المتابعة" value={numberFormat.format(dashboard?.pending||0)} note="تحتاج متابعة" tone="stat-amber"/>
            <StatCard label="جارٍ التنفيذ" value={numberFormat.format(dashboard?.in_progress||0)} note="تعمل عليها الفرق" tone="stat-purple"/>
            <StatCard label="مكتملة" value={numberFormat.format(dashboard?.completed||0)} note="تم إغلاقها" tone="stat-green"/>
          </section>
          <div className="dashboard-grid"><section className="panel response-panel"><div className="panel-heading"><div><span className="eyebrow">مؤشرات التشغيل</span><h2>حالة العمليات</h2></div><span className="unit-badge">مؤشر مباشر</span></div><div className="response-number">{dashboard?.avg_response_minutes==null?'—':numberFormat.format(dashboard.avg_response_minutes)}<small>متوسط زمن الاستجابة</small></div><div className="distribution-list">{[['قيد المتابعة',dashboard?.pending||0,'#d5a35d'],['جارٍ التنفيذ',dashboard?.in_progress||0,'#8f82b8'],['مكتملة',dashboard?.completed||0,'#52a184']].map(([label,value,color])=><div className="distribution-item" key={label}><div><span>{label}</span><b>{numberFormat.format(value)}</b></div><div className="distribution-track"><i style={{width:`${dashboard?.total?Math.min(100,value/dashboard.total*100):0}%`,background:color}}/></div></div>)}</div></section>
            <section className="panel recent-panel"><div className="panel-heading"><div><span className="eyebrow">آخر التحديثات</span><h2>عمليات حديثة</h2></div><button className="subtle-link" onClick={()=>setPage('operations')}>عرض السجل <Icon name="arrow"/></button></div><RecordsTable records={records.slice(0,5)} user={user} onStatus={changeStatus} onValidate={validateRecord}/></section></div>
        </>}
        {page==='operations'&&<>
          {createOpen&&<form className="panel create-form" onSubmit={createOperation}><div className="form-heading"><div><span className="eyebrow">سجل جديد</span><h2>تفاصيل العملية</h2></div></div><div className="form-grid"><label>وصف العملية<input required minLength="2" value={createForm.title} onChange={e=>setCreateForm({...createForm,title:e.target.value})} placeholder="مثال: بلاغ مروري"/></label><label>الفئة<input required value={createForm.category} onChange={e=>setCreateForm({...createForm,category:e.target.value})} placeholder="مرور، دورية…"/></label><label>المنطقة<input required value={createForm.region} onChange={e=>setCreateForm({...createForm,region:e.target.value})} placeholder="المنطقة أو الحي"/></label><label>الأولوية<select value={createForm.priority} onChange={e=>setCreateForm({...createForm,priority:e.target.value})}><option>عادي</option><option>منخفض</option><option>مرتفع</option><option>عاجل</option></select></label></div><button className="button button-primary">حفظ العملية</button></form>}
          <section className="panel records-panel"><div className="panel-heading"><div><span className="eyebrow">السجل التشغيلي</span><h2>العمليات المسجلة</h2></div><span className="count-badge">{numberFormat.format(records.length)} سجل</span></div><RecordsTable records={records} user={user} onStatus={changeStatus} onValidate={validateRecord}/></section>
        </>}
        {page==='users'&&canManageUsers&&<><section className="role-catalog-section"><div className="panel-heading"><div><span className="eyebrow">نموذج الصلاحيات</span><h2>ماذا يستطيع كل دور أن يفعل؟</h2></div><span className="count-badge">{roleCatalog.length} أدوار</span></div><div className="role-catalog-grid">{roleCatalog.map(item=><article className={`role-card role-card-${item.role}`} key={item.role}><div><span className={`role-tag role-${item.role}`}>{item.label}</span><p>{item.description}</p></div><ul>{item.capabilities.map(capability=><li key={capability}>{capability}</li>)}</ul></article>)}</div></section><section className="panel employee-create-panel"><div className="panel-heading"><div><span className="eyebrow">إضافة موظف</span><h2>إنشاء حساب جديد</h2><p>حدّد الدور وكلمة مرور أولية من ١٢ حرفًا على الأقل. سيُطلب من الموظف تغييرها عند أول دخول.</p></div></div><form className="workflow-form" onSubmit={createEmployee}><div className="form-grid"><label>اسم الموظف<input required minLength="2" value={employeeForm.name} onChange={e=>setEmployeeForm({...employeeForm,name:e.target.value})}/></label><label>البريد الإلكتروني<input required type="email" dir="ltr" value={employeeForm.email} onChange={e=>setEmployeeForm({...employeeForm,email:e.target.value})}/></label><label>الدور<select value={employeeForm.role} onChange={e=>setEmployeeForm({...employeeForm,role:e.target.value})}><option value="officer">ضابط</option><option value="police_commander">قائد الشرطة</option><option value="mayor">العمدة</option></select></label><label>كلمة المرور الأولية<input required minLength="12" type="password" autoComplete="new-password" dir="ltr" value={employeeForm.temporary_password} onChange={e=>setEmployeeForm({...employeeForm,temporary_password:e.target.value})}/></label></div><button className="button button-primary" disabled={employeeBusy}><Icon name="plus"/>{employeeBusy?'جارٍ إنشاء الحساب…':'إنشاء الحساب'}</button></form></section><section className="panel users-panel"><div className="panel-heading"><div><span className="eyebrow">حسابات الموظفين</span><h2>الحسابات والصلاحيات</h2><p>غيّر دور الموظف لتحديث صلاحياته. دور مسؤول قواعد البيانات محجوز للحساب الأول.</p></div><span className="count-badge">{numberFormat.format(users.length)} حساب</span></div><div className="table-scroll"><table><thead><tr><th>الحساب</th><th>الدور</th><th>ما يستطيع فعله</th><th>تعيين دور</th></tr></thead><tbody>{users.map(row=><tr key={row.id}><td><b>{row.name}</b><small>{row.email}</small>{row.must_change_password&&<small className="password-pending">بانتظار تغيير كلمة المرور</small>}</td><td><span className={`role-tag role-${row.role}`}>{roleNames[row.role]}</span></td><td><details className="permission-details"><summary>{row.permissions?.length||0} صلاحيات</summary><ul>{(row.permissions||[]).map(permission=><li key={permission}>{permission}</li>)}</ul></details></td><td>{row.role==='data_analyst'?<span className="fixed-role"><Icon name="lock"/> مسؤول النظام</span>:<select disabled={roleBusy===row.id} value={row.role} onChange={e=>changeRole(row.id,e.target.value)}><option value="mayor">العمدة</option><option value="police_commander">قائد الشرطة</option><option value="officer">ضابط</option></select>}</td></tr>)}</tbody></table>{!users.length&&<div className="empty-state"><b>لا توجد حسابات بعد</b></div>}</div></section></>}{page==='users'&&canManageUsers&&<section className="panel history-panel"><div className="panel-heading"><div><span className="eyebrow">سجل إنشاء الحسابات</span><h2>الحسابات التي أُنشئت</h2></div><span className="count-badge">آخر ١٠٠ حساب</span></div>{accountHistory.length?<div className="table-scroll"><table><thead><tr><th>الموظف</th><th>الدور الأولي</th><th>أنشأه</th><th>التاريخ</th></tr></thead><tbody>{accountHistory.map(entry=><tr key={entry.id}><td><b>{entry.employee_name}</b><small>{entry.employee_email}</small></td><td>{entry.role_label}</td><td>{entry.creator_name}</td><td>{new Date(entry.created_at).toLocaleString('ar-SA')}</td></tr>)}</tbody></table></div>:<div className="history-empty">لم تُنشأ حسابات من صفحة الصلاحيات بعد.</div>}</section>}{page==='users'&&canManageUsers&&<section className="panel history-panel"><div className="panel-heading"><div><span className="eyebrow">سجل التدقيق</span><h2>تغييرات الصلاحيات</h2></div><span className="count-badge">آخر ١٠٠ تغيير</span></div>{roleHistory.length?<div className="table-scroll"><table><thead><tr><th>الحساب</th><th>تغيير بواسطة</th><th>من</th><th>إلى</th><th>التاريخ</th></tr></thead><tbody>{roleHistory.map(entry=><tr key={entry.id}><td><b>{entry.target_name}</b><small>{entry.target_email}</small></td><td>{entry.actor_name}</td><td>{entry.previous_role_label}</td><td>{entry.new_role_label}</td><td>{new Date(entry.changed_at).toLocaleString('ar-SA')}</td></tr>)}</tbody></table></div>:<div className="history-empty">لم تُسجل تغييرات بعد.</div>}</section>}
        {page==='change-requests'&&canManageUsers&&<section className="panel records-panel"><div className="panel-heading"><div><span className="eyebrow">مراجعة التعديلات السابقة</span><h2>طلبات الضباط</h2><p>التعديل على سجل سبق تغييره لا ينفذ قبل اعتمادك.</p></div><span className="count-badge">{numberFormat.format(changeRequests.length)} طلب</span></div>{changeRequests.length?changeRequests.map(row=><article className="workflow-card" key={row.id}><div><h3>{row.operation_title} · #{row.operation_id}</h3><p>طلب من {row.requested_by_name} · النسخة الحالية {row.current_version} · المطلوبة {row.expected_version}</p><pre dir="ltr">{JSON.stringify(row.changes,null,2)}</pre></div><div className="inline-actions"><button className="button button-primary" onClick={()=>reviewChange(row.id,true)}>اعتماد</button><button className="button button-secondary" onClick={()=>reviewChange(row.id,false)}>رفض</button></div></article>):<div className="empty-state"><b>لا توجد تعديلات معلّقة</b></div>}</section>}
        {page==='data-requests'&&<section className="panel records-panel"><div className="panel-heading"><div><span className="eyebrow">مسار الطلبات</span><h2>{user.role==='mayor'?'اطلب بيانات':'طلبات البيانات'}</h2><p>{user.role==='mayor'?'يستلم قائد الشرطة طلبك ويوجهه للموظف المناسب، ثم يراجع النتيجة قبل ظهورها.':'تُراجع الإجابات من قائد الشرطة قبل عرضها للعمدة.'}</p></div></div>{user.role==='mayor'&&<form className="workflow-form" onSubmit={createMayorRequest}><label>عنوان الطلب<input required value={requestForm.title} onChange={e=>setRequestForm({...requestForm,title:e.target.value})}/></label><label>ما البيانات المطلوبة؟<textarea required minLength="5" value={requestForm.question} onChange={e=>setRequestForm({...requestForm,question:e.target.value})}/></label><label>المستوى<select value={requestForm.complexity} onChange={e=>setRequestForm({...requestForm,complexity:e.target.value})}><option value="standard">اعتيادي</option><option value="advanced">متقدم</option></select></label><button className="button button-primary">إرسال الطلب</button></form>}{dataRequests.map(row=><article className="workflow-card" key={row.id}><div><h3>{row.title}</h3><p>{row.question}</p><span className="status-pill">{({pending_commander:'بانتظار توجيه القائد',routed_officer:'مسند للضابط',routed_analyst:'لدى مسؤول قواعد البيانات',pending_commander_review:'بانتظار مراجعة القائد',completed:'معتمد',rejected:'مرفوض'})[row.status]||row.status}</span>{row.result_text&&<p className="workflow-result">النتيجة: {row.result_text}</p>}</div>{user.role==='police_commander'&&row.status==='pending_commander'&&<div className="inline-actions"><button className="button button-primary" onClick={()=>routeRequest(row.id,'officer')}>توجيه للضابط</button><button className="button button-secondary" onClick={()=>routeRequest(row.id,'data_analyst')}>إرسال للمحلل</button></div>}{user.role==='police_commander'&&row.status==='pending_commander_review'&&<div className="inline-actions"><button className="button button-primary" onClick={()=>reviewRequest(row.id,true)}>اعتماد النتيجة</button><button className="button button-secondary" onClick={()=>reviewRequest(row.id,false)}>رفض</button></div>}{['officer','data_analyst'].includes(user.role)&&row.status===(user.role==='officer'?'routed_officer':'routed_analyst')&&<form className="workflow-answer" onSubmit={e=>submitRequestResult(e,row.id)}><textarea required minLength="3" value={draftResults[row.id]||''} onChange={e=>setDraftResults({...draftResults,[row.id]:e.target.value})} placeholder="اكتب النتيجة أو ملخص البيانات"/><button className="button button-primary">إرسال للقائد للمراجعة</button>{user.role==='officer'&&<button type="button" className="text-action" onClick={()=>escalateRequest(row.id)}>تصعيد للمحلل</button>}</form>}</article>)}{!dataRequests.length&&<div className="empty-state"><b>{user.role==='mayor'?'لم ترسل طلبات بعد':'لا توجد طلبات في هذا المسار'}</b></div>}</section>}
        {page==='reports'&&<><section className="panel records-panel"><div className="panel-heading"><div><span className="eyebrow">الرسوم البيانية</span><h2>{user.role==='police_commander'?'مراجعة الرسوم':user.role==='mayor'?'الرسوم المعتمدة':'رسومي البيانية'}</h2><p>{user.role==='police_commander'?'اعتمد الرسم بعد التحقق من صحة المصدر وطريقة العرض.':user.role==='mayor'?'تظهر هنا الرسوم التي اعتمدها قائد الشرطة.':'أنشئ رسمًا من استعلام قراءة، ثم أرسله للقائد للمراجعة.'}</p></div></div>{['officer','data_analyst'].includes(user.role)&&<form className="workflow-form" onSubmit={createReport}><label>عنوان الرسم<input required value={reportForm.title} onChange={e=>setReportForm({...reportForm,title:e.target.value})}/></label><label>استعلام القراءة<textarea required dir="ltr" value={reportForm.statement} onChange={e=>setReportForm({...reportForm,statement:e.target.value})}/></label><div className="form-grid"><label>عمود الفئات<input required dir="ltr" value={reportForm.label_column} onChange={e=>setReportForm({...reportForm,label_column:e.target.value})}/></label><label>عمود الأرقام<input required dir="ltr" value={reportForm.value_column} onChange={e=>setReportForm({...reportForm,value_column:e.target.value})}/></label></div><button className="button button-primary">إنشاء الرسم وإرساله للمراجعة</button></form>}{reports.map(report=><article className="workflow-card" key={report.id}><div><h3>{report.title}</h3><p>إعداد {report.author_name||'مسؤول قواعد البيانات'} · {report.status==='approved'?'معتمد':report.status==='pending_commander'?'بانتظار القائد':'مرفوض'}</p><div className="chart-bars">{(report.chart_data||[]).map((point,index)=>{const max=Math.max(1,...report.chart_data.map(item=>Number(item.value)||0));return <div key={index} className="chart-bar-row"><span>{point.label}</span><i><b style={{width:`${Math.max(2,Number(point.value)/max*100)}%`}}/></i><strong>{numberFormat.format(point.value)}</strong></div>})}</div>{report.review_note&&<p>{report.review_note}</p>}</div>{user.role==='police_commander'&&<div className="inline-actions"><button className="button button-primary" onClick={()=>reviewReport(report.id,true)}>اعتماد</button><button className="button button-secondary" onClick={()=>reviewReport(report.id,false)}>رفض</button></div>}</article>)}{!reports.length&&<div className="empty-state"><b>لا توجد رسوم متاحة</b></div>}</section></>}
        {page==='lab-tasks'&&<section className="spatial-labs">{spatialLabs.map(lab=><article className="panel lab-panel" key={lab.id}><div className="panel-heading"><div><span className="eyebrow">مختبر SQL · تدريب اصطناعي</span><h2>{lab.title}</h2><p dir="ltr">{lab.source}</p></div>{lab.exercises?.length>0&&<button className="button button-primary" onClick={()=>setPage('district-dashboard')}><Icon name="shield"/>فتح لوحة التسليم</button>}</div>{lab.tasks?.length>0&&<ol className="lab-task-list">{lab.tasks.map((task,index)=><li key={`${lab.id}-${index}`}><span className="lab-task-number">{index<4?`E${index+1}`:'✓'}</span><span>{task}</span></li>)}</ol>}{lab.exercises?.length>0&&<div className="lab-exercise-list">{lab.exercises.map(task=><article className="lab-exercise" key={task.id}><div><b>{task.title}</b><small>ينفذ باستعلام قراءة على {labDashboard?.database||'Police_training'}، ضمن صلاحيات حسابك.</small></div><button className="button button-secondary" disabled={labTaskBusy===task.id} onClick={()=>runLabTask(task.id)}>{labTaskBusy===task.id?'جارٍ التنفيذ…':'تنفيذ المهمة'}</button>{labTaskResults[task.id]&&<div className="lab-exercise-result"><code dir="ltr">{labTaskResults[task.id].statement}</code><LabTaskChart result={labTaskResults[task.id].result}/><SQLResults result={labTaskResults[task.id].result}/></div>}</article>)}</div>}{lab.daily&&<div className="lab-daily"><b>المهمة اليومية والتسليم</b><p>{lab.daily}</p></div>}{lab.rubric&&<p className="lab-rubric">{lab.rubric}</p>}{lab.exercises?.length>0&&<div className="sql-note lab-note"><Icon name="shield"/><span>كل الأدوار تستطيع تنفيذ هذه التمارين ومشاهدة رسومها على البيانات التدريبية الاصطناعية. تظل بيانات العمليات التشغيلية للعمدة محصورة بالسجلات المعتمدة.</span></div>}</article>)}</section>}
        {page==='district-dashboard'&&<section className="district-dashboard">{labDashboardBusy&&!labDashboard&&<div className="panel empty-state">جارٍ تحميل تحليل المناطق من قاعدة البيانات…</div>}{labDashboard&&<><section className="panel district-dashboard-header"><div><span className="eyebrow">تقرير تحليلي · 2025 · بيانات اصطناعية</span><h2>الجرائم والحوادث حسب المنطقة والشهر</h2><p>قاعدة البيانات: <b dir="ltr">{labDashboard.database}</b> · {labDashboard.monthly.length} شهرًا · {labDashboard.districts.length} مناطق · توليد {new Date(labDashboard.generated_at).toLocaleString('ar-SA')}</p></div><div className="inline-actions"><button className="button button-primary" onClick={downloadMonthlyCsv}>تنزيل CSV</button><button className="button button-secondary" onClick={downloadProvenance}>تنزيل provenance JSON</button></div></section><section className="reconciliation-grid">{Object.entries(labDashboard.checks).map(([key,passed])=><article className={`reconciliation-card ${passed?'passed':'failed'}`} key={key}><span>{passed?'✓':'!'}</span><b>{{crime_source_matches_assignment:'مطابقة مصدر الجرائم',crime_assignment_matches_report:'مطابقة الجرائم مع التقرير',traffic_source_matches_assignment:'مطابقة مصدر الحوادث',traffic_assignment_matches_report:'مطابقة الحوادث مع التقرير',district_month_calendar_complete:'اكتمال تقويم المنطقة والشهر'}[key]}</b></article>)}</section><section className="lab-chart-grid"><article className="panel"><div className="panel-heading"><div><span className="eyebrow">مجموعات شهرية</span><h2>الجرائم والحوادث</h2></div></div><div className="lab-bars">{labDashboard.monthly.map(row=>{const maximum=Math.max(1,...labDashboard.monthly.map(item=>Math.max(Number(item.crimes)||0,Number(item.crashes)||0)));return <div className="lab-bar-group" key={row.month}><b>{String(row.month).slice(5,7)}</b><div className="lab-bar-pair"><i className="crime-bar" style={{height:`${Math.max(3,Number(row.crimes)/maximum*100)}%`}} title={`جرائم ${row.crimes}`}/><i className="crash-bar" style={{height:`${Math.max(3,Number(row.crashes)/maximum*100)}%`}} title={`حوادث ${row.crashes}`}/></div><small>{numberFormat.format(row.crimes)} / {numberFormat.format(row.crashes)}</small></div>})}</div><div className="chart-legend"><span><i className="crime-bar"/> جرائم</span><span><i className="crash-bar"/> حوادث</span></div></article><article className="panel"><div className="panel-heading"><div><span className="eyebrow">ملخص المناطق</span><h2>الحوادث والإصابات</h2></div></div><div className="table-scroll"><table><thead><tr><th>المنطقة</th><th>الجرائم</th><th>الحوادث</th><th>قياسات الإصابات</th><th>مجموع الإصابات</th><th>متوسط الإصابة</th></tr></thead><tbody>{labDashboard.districts.map(row=><tr key={row.dist_num}><td>{row.dist_num}</td><td>{numberFormat.format(row.crimes)}</td><td>{numberFormat.format(row.crashes)}</td><td>{numberFormat.format(row.observed_injuries)}</td><td>{row.injuries==null?'—':numberFormat.format(row.injuries)}</td><td>{row.mean_injuries==null?'—':numberFormat.format(row.mean_injuries)}</td></tr>)}</tbody></table></div></article></section><section className="panel records-panel coverage-panel"><div className="panel-heading"><div><span className="eyebrow">حفظ المقام والتحقق</span><h2>تغطية المصدرين ومطابقة الأعداد</h2><p>الصفوف غير المطابقة تبقى في مقام المصدر، ولا تختلط الجرائم بالحوادث.</p></div></div><div className="table-scroll"><table><thead><tr><th>المصدر</th><th>الإجمالي</th><th>أُسندت لمنطقة</th><th>غير مطابقة</th></tr></thead><tbody>{labDashboard.coverage.map(row=><tr key={row.source}><td>{row.source==='crime'?'الجرائم':'الحوادث المرورية'}</td><td>{numberFormat.format(row.total)}</td><td>{numberFormat.format(row.assigned)}</td><td>{numberFormat.format(row.unmatched)}</td></tr>)}</tbody></table></div></section><section className="panel handover-panel"><div className="panel-heading"><div><span className="eyebrow">تسليم التقرير</span><h2>ملاحظات العرض لمدة خمس دقائق</h2><p>اكتب قرار مستوى الصفوف، وبديلًا فاشلًا، ونتيجة تحقق، وقيدًا واحدًا. ستُرفق ملاحظاتك بملف provenance JSON.</p></div></div><textarea value={handoverNote} onChange={e=>setHandoverNote(e.target.value)} placeholder="مثال: صف واحد لكل منطقة وشهر؛ قارنت مجموع المصدر مع التقرير؛ غياب الإحداثيات يحد من التغطية…"/><div className="reconciliation-evidence"><b>أدلة المطابقة</b><p>الجرائم: {labDashboard.reconciliation.assigned_crimes} مسندة + {labDashboard.reconciliation.unmatched_crimes} غير مطابقة = {labDashboard.reconciliation.source_crimes} من المصدر.</p><p>الحوادث: {labDashboard.reconciliation.assigned_crashes} مسندة + {labDashboard.reconciliation.unmatched_crashes} غير مطابقة = {labDashboard.reconciliation.source_crashes} من المصدر.</p><p>التقرير: {labDashboard.reconciliation.report_rows} صف منطقة-شهر من أصل {labDashboard.reconciliation.expected_rows} متوقع.</p></div></section></>}</section>}
        {page==='command-log'&&canManageUsers&&<section className="panel records-panel"><div className="panel-heading"><div><span className="eyebrow">سجل محلي مشفّر</span><h2>حالة أوامر SQL</h2><p>تُراجع صلاحية صاحب الأمر قبل إعادة تشغيله، ويُسجل نجاحه أو سبب تعذره.</p></div><button className="button button-secondary" onClick={()=>api('/api/sql-console/commands').then(setCommandHistory).catch(exception=>setError(exception.message))}>تحديث السجل</button></div>{commandHistory.length?<div className="table-scroll"><table><thead><tr><th>الأمر</th><th>الحالة</th><th>عدد المحاولات</th><th>آخر نتيجة أو خطأ</th><th>آخر تحديث</th></tr></thead><tbody>{commandHistory.map(item=><tr key={item.command_id}><td><code dir="ltr">{item.statement}</code><small>{item.command_id}</small></td><td><span className={`status-pill ${item.status==='applied'?'done':''}`}>{({queued:'بانتظار الاتصال',running:'جارٍ التنفيذ',applied:'تم التنفيذ',failed:'تعذر التنفيذ'})[item.status]||item.status}</span></td><td>{numberFormat.format(item.attempts)}</td><td>{item.last_error|| (item.result?`تم التنفيذ · ${numberFormat.format(item.result.affected_rows||0)} صف`:'—')}</td><td>{new Date(item.updated_at).toLocaleString('ar-SA')}</td></tr>)}</tbody></table></div>:<div className="empty-state"><b>لا توجد أوامر في السجل بعد</b><p>ستظهر هنا الأوامر المنفذة من محرر SQL والأوامر المحفوظة عند الانقطاع.</p></div>}</section>}
        {page==='sql'&&canSql&&<div className="sql-page"><section className="panel sql-panel"><div className="panel-heading"><div><span className="eyebrow">أدوات البيانات</span><h2>محرر SQL</h2><p>{user.role==='data_analyst'?'لديك صلاحية تعديل بيانات العمليات والتدريب وإنشاء الجداول.':user.role==='mayor'?'استعلامات قراءة للبيانات المعتمدة فقط.':user.role==='officer'?'استعلامات قراءة لسجلاتك وبيانات التدريب؛ الإضافة والتعديل عبر النماذج المحددة.':'استعلامات قراءة لجميع السجلات وبيانات التدريب.'}</p></div><span className={`sql-badge ${sqlConnection?.connected?'connection-live':'connection-offline'}`}><i/>{sqlConnection?.connected?`متصل · ${sqlConnection.database}`:sqlConnection?'Neon غير متصل · ستُحفظ الأوامر':'يتحقق من اتصال Neon…'}</span></div><form onSubmit={runSQL}><label className="sql-label" htmlFor="sql-editor">الاستعلام</label><textarea id="sql-editor" className="sql-editor" dir="ltr" spellCheck="false" value={sql} onChange={e=>setSql(e.target.value)}/><div className="sql-actions"><span>حد أقصى ٥٠٠ صف · مهلة ١٠ ثوانٍ</span><button className="button button-primary" disabled={sqlBusy||!sql.trim()}><Icon name="sql"/>{sqlBusy?'جارٍ التنفيذ…':'تشغيل الاستعلام'}</button></div></form></section>
          <div className="sql-note"><Icon name="shield"/><span>{user.role==='data_analyst'?'استعلاماتك تنفذ مباشرة على Police_training بصلاحية إدارة بيانات العمليات والتدريب.':'يُنفذ SQL على Police_training بوضع القراءة فقط؛ يقيّد الخادم وقاعدة البيانات الصفوف والمخططات حسب دورك.'}</span></div>
          {sqlResult&&<SQLResults result={sqlResult}/>}
        </div>}
      </div>
      <footer className="page-footer"><span>مِرْصاد</span><span>تُطبّق الصلاحيات على الخادم وقاعدة البيانات</span></footer>
    </main>
  </div>
}

export default function Home() {
  const [user, setUser] = useState(null)
  const [canRegister, setCanRegister] = useState(false)
  const [loading, setLoading] = useState(true)
  useEffect(()=>{Promise.all([api('/api/auth/me').then(setUser).catch(()=>{}),api('/api/auth/registration-status').then(result=>setCanRegister(result.allowed)).catch(()=>{})]).finally(()=>setLoading(false))},[])
  async function logout() { await api('/api/auth/logout',{method:'POST'}).catch(()=>{}); setUser(null) }
  if (loading) return <div className="loading-screen"><div className="loading-mark"><Icon name="shield"/></div><span>يتم تجهيز مساحة العمل</span></div>
  return user ? (user.must_change_password ? <ChangePassword user={user} onChanged={setUser}/> : <AppShell user={user} onLogout={logout}/>) : <Auth onLogin={setUser} canRegister={canRegister}/>
}
