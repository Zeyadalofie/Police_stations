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
  police_commander: 'متابعة العمليات ومؤشرات أداء الفرق',
  officer: 'تسجيل العمليات ومتابعة مهامك',
  mayor: 'عرض مؤشرات وملخصات العمليات',
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

function Auth({ onLogin }) {
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
    <section className="auth-form-panel"><div className="auth-card"><span className="eyebrow">مرحبًا بك</span><h2>{register ? 'أنشئ حسابك' : 'تسجيل الدخول'}</h2><p className="muted">{register ? 'ستبدأ بحساب ضابط، ويحدد المسؤول صلاحيتك.' : 'سجّل الدخول للوصول إلى مساحة العمل الخاصة بك.'}</p>
      <form onSubmit={submit} className="auth-form">
        {register && <label>الاسم الكامل<input required minLength="2" autoComplete="name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})} placeholder="اكتب اسمك"/></label>}
        <label>البريد الإلكتروني<input required type="email" autoComplete="email" value={form.email} onChange={e=>setForm({...form,email:e.target.value})} placeholder="name@example.com" dir="ltr"/></label>
        <label>كلمة المرور<input required minLength="8" type="password" autoComplete={register?'new-password':'current-password'} value={form.password} onChange={e=>setForm({...form,password:e.target.value})} placeholder="٨ أحرف على الأقل" dir="ltr"/></label>
        {error && <div className="inline-error" role="alert">{error}</div>}
        <button className="button button-primary button-wide" disabled={busy}>{busy?'جارٍ الدخول…':register?'إنشاء الحساب':'دخول إلى مساحة العمل'}<Icon name="arrow"/></button>
      </form>
      <div className="auth-toggle">{register?'لديك حساب بالفعل؟':'ليس لديك حساب؟'} <button onClick={()=>{setError('');setMode(register?'login':'register')}}>{register?'سجّل الدخول':'أنشئ حسابًا'}</button></div>
      <div className="auth-privacy"><Icon name="lock"/><span>تُحمى الجلسات وتُطبّق صلاحيات الحساب من الخادم.</span></div>
    </div></section>
  </main>
}

function StatCard({ label, value, note, tone }) {
  return <article className={`stat-card ${tone || ''}`}><div className="stat-label">{label}<span className="stat-dot"/></div><strong>{value ?? '—'}</strong><small>{note}</small></article>
}

function RecordsTable({ records, user, onStatus }) {
  const canManage = ['police_commander', 'data_analyst'].includes(user.role)
  if (!records.length) return <div className="empty-state"><div className="empty-mark"><Icon name="file"/></div><b>لا توجد عمليات مسجلة بعد</b><p>ستظهر السجلات هنا بعد إضافتها إلى النظام.</p></div>
  return <div className="table-scroll"><table><thead><tr><th>العملية</th><th>المنطقة</th><th>الأولوية</th><th>الحالة</th><th>زمن الاستجابة</th><th>وقت التسجيل</th></tr></thead><tbody>{records.map(row=><tr key={row.id}>
    <td><b>{row.title}</b><small>{row.category} · #{row.id}</small></td><td>{row.region}</td><td><span className={`priority priority-${row.priority==='عاجل'?'urgent':row.priority==='مرتفع'?'high':'normal'}`}>{row.priority}</span></td>
    <td>{canManage?<select className="status-select" value={row.status} onChange={e=>onStatus(row.id,e.target.value)}><option>قيد المتابعة</option><option>جارٍ التنفيذ</option><option>مكتملة</option></select>:<span className={`status-pill ${row.status==='مكتملة'?'done':''}`}>{row.status}</span>}</td>
    <td>{row.response_minutes == null ? '—' : `${numberFormat.format(row.response_minutes)} د`}</td><td>{new Date(row.occurred_at).toLocaleDateString('ar-SA')}</td>
  </tr>)}</tbody></table></div>
}

function SQLResults({ result }) {
  if (!result) return null
  return <div className="query-result">
    <div className="result-top"><div><b>{result.columns.length?'نتيجة الاستعلام':'اكتمل تنفيذ الأمر'}</b><span>{result.columns.length?`${numberFormat.format(result.affected_rows)} صف`:`${numberFormat.format(result.affected_rows)} صف متأثر`}{result.truncated?' · عُرض أول ٥٠٠ صف':''}</span></div><span className="result-check"><Icon name="check"/> مكتمل</span></div>
    {result.columns.length ? <div className="table-scroll"><table className="sql-table" dir="ltr"><thead><tr>{result.columns.map(c=><th key={c}>{c}</th>)}</tr></thead><tbody>{result.rows.map((row,i)=><tr key={i}>{row.map((v,j)=><td key={j}>{v===null?<i>NULL</i>:String(v)}</td>)}</tr>)}</tbody></table>{!result.rows.length&&<div className="no-rows">الاستعلام لم يُرجع صفوفًا.</div>}</div>:<div className="command-complete">تم تنفيذ الأمر بنجاح.</div>}
  </div>
}

function AppShell({ user, onLogout }) {
  const [page, setPage] = useState('overview')
  const [dashboard, setDashboard] = useState(null)
  const [records, setRecords] = useState([])
  const [users, setUsers] = useState([])
  const [roleHistory, setRoleHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const [sql, setSql] = useState('SELECT id, title, category, region, status\nFROM operation_records\nORDER BY occurred_at DESC\nLIMIT 20;')
  const [sqlResult, setSqlResult] = useState(null)
  const [sqlBusy, setSqlBusy] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState({ title: '', category: '', region: '', priority: 'عادي' })
  const [roleBusy, setRoleBusy] = useState(null)
  const canSql = user.role !== 'mayor'
  const canManageUsers = user.role === 'data_analyst'
  const canCreate = ['officer', 'police_commander', 'data_analyst'].includes(user.role)
  const nav = useMemo(() => [
    { id: 'overview', label: 'نظرة عامة', icon: 'home' },
    { id: 'operations', label: user.role === 'mayor' ? 'سجل العمليات' : 'العمليات', icon: 'file' },
    ...(canSql ? [{ id: 'sql', label: 'استعلامات SQL', icon: 'sql' }] : []),
    ...(canManageUsers ? [{ id: 'users', label: 'الحسابات والصلاحيات', icon: 'users' }] : []),
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
    if (page !== 'users' || !canManageUsers) return
    Promise.all([api('/api/admin/users'),api('/api/admin/role-history')]).then(([accounts,history])=>{setUsers(accounts);setRoleHistory(history)}).catch(exception=>setError(exception.message))
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

  async function changeRole(id, role) {
    setRoleBusy(id); setError(''); setNotice('')
    try {
      await api(`/api/admin/users/${id}/role`, { method: 'PUT', body: JSON.stringify({ role }) })
      setUsers(current=>current.map(row=>row.id===id?{...row,role,role_label:roleNames[role]}:row)); setRoleHistory(await api('/api/admin/role-history')); setNotice('تم تحديث صلاحية الحساب')
    } catch (exception) { setError(exception.message); await api('/api/admin/users').then(setUsers).catch(()=>{}) }
    finally { setRoleBusy(null) }
  }

  async function runSQL(event) {
    event.preventDefault(); setSqlBusy(true); setSqlResult(null); setError(''); setNotice('')
    try { setSqlResult(await api('/api/sql-console/execute', { method: 'POST', body: JSON.stringify({ statement: sql }) })) }
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
        <div className="page-heading"><div><span className="eyebrow">{roleNames[user.role]}</span><h1>{page==='overview'?`أهلًا، ${name}`:pageTitle}</h1><p>{page==='overview'?roleDescriptions[user.role]:page==='sql'?'اكتب استعلامك، وستُطبق قاعدة البيانات حدود صلاحيتك.':page==='users'?'عيّن دور كل حساب وراجع سجل تغييرات الصلاحيات.':'تابع السجلات وفق صلاحية حسابك.'}</p></div>
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
            <section className="panel recent-panel"><div className="panel-heading"><div><span className="eyebrow">آخر التحديثات</span><h2>عمليات حديثة</h2></div><button className="subtle-link" onClick={()=>setPage('operations')}>عرض السجل <Icon name="arrow"/></button></div><RecordsTable records={records.slice(0,5)} user={user} onStatus={changeStatus}/></section></div>
        </>}
        {page==='operations'&&<>
          {createOpen&&<form className="panel create-form" onSubmit={createOperation}><div className="form-heading"><div><span className="eyebrow">سجل جديد</span><h2>تفاصيل العملية</h2></div></div><div className="form-grid"><label>وصف العملية<input required minLength="2" value={createForm.title} onChange={e=>setCreateForm({...createForm,title:e.target.value})} placeholder="مثال: بلاغ مروري"/></label><label>الفئة<input required value={createForm.category} onChange={e=>setCreateForm({...createForm,category:e.target.value})} placeholder="مرور، دورية…"/></label><label>المنطقة<input required value={createForm.region} onChange={e=>setCreateForm({...createForm,region:e.target.value})} placeholder="المنطقة أو الحي"/></label><label>الأولوية<select value={createForm.priority} onChange={e=>setCreateForm({...createForm,priority:e.target.value})}><option>عادي</option><option>منخفض</option><option>مرتفع</option><option>عاجل</option></select></label></div><button className="button button-primary">حفظ العملية</button></form>}
          <section className="panel records-panel"><div className="panel-heading"><div><span className="eyebrow">السجل التشغيلي</span><h2>العمليات المسجلة</h2></div><span className="count-badge">{numberFormat.format(records.length)} سجل</span></div><RecordsTable records={records} user={user} onStatus={changeStatus}/></section>
        </>}
        {page==='users'&&canManageUsers&&<section className="panel users-panel"><div className="panel-heading"><div><span className="eyebrow">إدارة الفريق</span><h2>الحسابات والصلاحيات</h2><p>حساب مسؤول قواعد البيانات ثابت، ولا يمكن تغييره من هذه القائمة.</p></div><span className="count-badge">{numberFormat.format(users.length)} حساب</span></div><div className="table-scroll"><table><thead><tr><th>الحساب</th><th>الدور الحالي</th><th>الصلاحية الجديدة</th><th>الحالة</th></tr></thead><tbody>{users.map(row=><tr key={row.id}><td><b>{row.name}</b><small>{row.email}</small></td><td><span className={`role-tag role-${row.role}`}>{roleNames[row.role]}</span></td><td>{row.role==='data_analyst'?<span className="fixed-role"><Icon name="lock"/> مسؤول النظام</span>:<select disabled={roleBusy===row.id} value={row.role} onChange={e=>changeRole(row.id,e.target.value)}><option value="mayor">العمدة</option><option value="police_commander">قائد الشرطة</option><option value="officer">ضابط</option></select>}</td><td><span className="active-state"><i/> نشط</span></td></tr>)}</tbody></table>{!users.length&&<div className="empty-state"><b>لا توجد حسابات بعد</b></div>}</div></section>}{page==='users'&&canManageUsers&&<section className="panel history-panel"><div className="panel-heading"><div><span className="eyebrow">سجل التدقيق</span><h2>تغييرات الصلاحيات</h2></div><span className="count-badge">آخر ١٠٠ تغيير</span></div>{roleHistory.length?<div className="table-scroll"><table><thead><tr><th>الحساب</th><th>تغيير بواسطة</th><th>من</th><th>إلى</th><th>التاريخ</th></tr></thead><tbody>{roleHistory.map(entry=><tr key={entry.id}><td><b>{entry.target_name}</b><small>{entry.target_email}</small></td><td>{entry.actor_name}</td><td>{entry.previous_role_label}</td><td>{entry.new_role_label}</td><td>{new Date(entry.changed_at).toLocaleString('ar-SA')}</td></tr>)}</tbody></table></div>:<div className="history-empty">لم تُسجل تغييرات بعد.</div>}</section>}
        {page==='sql'&&canSql&&<div className="sql-page"><section className="panel sql-panel"><div className="panel-heading"><div><span className="eyebrow">أدوات البيانات</span><h2>محرر SQL</h2><p>{user.role==='data_analyst'?'لديك صلاحية تعديل سجلات العمليات وإنشاء جداول في مساحة المحلل.':'استعلامات القراءة متاحة ضمن نطاق دورك.'}</p></div><span className="sql-badge"><i/> PostgreSQL</span></div><form onSubmit={runSQL}><label className="sql-label" htmlFor="sql-editor">الاستعلام</label><textarea id="sql-editor" className="sql-editor" dir="ltr" spellCheck="false" value={sql} onChange={e=>setSql(e.target.value)}/><div className="sql-actions"><span>حد أقصى ٥٠٠ صف · مهلة ١٠ ثوانٍ</span><button className="button button-primary" disabled={sqlBusy||!sql.trim()}><Icon name="sql"/>{sqlBusy?'جارٍ التنفيذ…':'تشغيل الاستعلام'}</button></div></form></section>
          <div className="sql-note"><Icon name="shield"/><span>{user.role==='data_analyst'?'تُنفذ استعلاماتك بدور قاعدة بيانات مقيّد؛ لا يمكنك إدارة أدوار PostgreSQL أو قراءة جداول الحسابات.':'تعمل استعلاماتك بصلاحية قراءة. يقيّد الخادم الوصول إلى سجلاتك أو سجلات القيادة حسب دورك.'}</span></div>
          {sqlResult&&<SQLResults result={sqlResult}/>}
        </div>}
      </div>
      <footer className="page-footer"><span>مِرْصاد</span><span>تُطبّق الصلاحيات على الخادم وقاعدة البيانات</span></footer>
    </main>
  </div>
}

export default function Home() {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  useEffect(()=>{api('/api/auth/me').then(setUser).catch(()=>{}).finally(()=>setLoading(false))},[])
  async function logout() { await api('/api/auth/logout',{method:'POST'}).catch(()=>{}); setUser(null) }
  if (loading) return <div className="loading-screen"><div className="loading-mark"><Icon name="shield"/></div><span>يتم تجهيز مساحة العمل</span></div>
  return user ? <AppShell user={user} onLogout={logout}/> : <Auth onLogin={setUser}/>
}
