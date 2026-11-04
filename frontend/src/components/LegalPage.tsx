import Link from "next/link";

export function LegalPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-screen bg-khata-canvas text-khata-ink">
      <header className="border-b border-khata-subtle bg-white px-6 py-3">
        <Link href="/" className="inline-flex items-center gap-2.5 text-sm font-bold">
          <span className="w-7 h-7 rounded-md bg-brand-500 text-white flex items-center justify-center font-devanagari">
            स
          </span>
          Saath
        </Link>
      </header>

      <article className="max-w-2xl mx-auto px-6 py-10 text-sm leading-relaxed [&_h2]:text-base [&_h2]:font-bold [&_h2]:mt-8 [&_h2]:mb-2 [&_p]:mb-3 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-3 [&_li]:mb-1 [&_a]:text-brand-700 [&_a]:underline">
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        <p className="text-xs text-khata-muted mt-1 mb-8">Last updated: {updated}</p>
        {children}
      </article>

      <footer className="border-t border-khata-subtle px-6 py-4 text-xs text-khata-muted flex gap-4 justify-center">
        <Link href="/privacy" className="hover:text-khata-ink">Privacy Policy</Link>
        <Link href="/terms" className="hover:text-khata-ink">Terms of Use</Link>
        <Link href="/" className="hover:text-khata-ink">Back to board</Link>
      </footer>
    </main>
  );
}
