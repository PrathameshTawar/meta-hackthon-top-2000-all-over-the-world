import { Board } from "@/components/Board";

// Default to household 1 for the demo.
// In production, derive from auth/session.
const HOUSEHOLD_ID = 1;

export default function HomePage() {
  return (
    <main className="min-h-screen">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Logo mark */}
          <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center text-white font-bold text-sm">
            स
          </div>
          <span className="text-lg font-semibold tracking-tight">
            Saath <span className="text-gray-400 font-normal text-sm">/ साथ</span>
          </span>
        </div>
        <span className="text-xs text-gray-400">Family coordination board</span>
      </header>

      <Board householdId={HOUSEHOLD_ID} />
    </main>
  );
}
