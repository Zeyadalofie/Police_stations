import './globals.css'

export const metadata = {
  title: 'مرصد | عمليات الشرطة',
  description: 'مساحة تحليل ومتابعة العمليات حسب صلاحية كل حساب',
}

export default function RootLayout({ children }) {
  return <html lang="ar" dir="rtl"><body>{children}</body></html>
}
