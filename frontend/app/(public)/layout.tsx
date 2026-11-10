import Link from "next/link";
import QuickExit from "./quick-exit";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3">
          <Link href="/" className="text-lg font-semibold text-teal-800">
            Vela Client Services
          </Link>
          <Link href="/login" className="text-sm text-slate-600 underline">
            Staff sign in
          </Link>
        </div>
      </header>
      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8">{children}</main>
      <QuickExit />
    </>
  );
}
