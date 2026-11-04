"use client";

export function BoardSkeleton() {
  return (
    <div className="flex flex-col h-[calc(100vh-65px)] bg-khata-canvas overflow-hidden">
      {/* 1. Warm Branded Loading Banner / Transition Bar */}
      <div className="bg-brand-50/60 border-b border-brand-200/50 px-6 py-2 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="relative flex items-center justify-center w-6 h-6 rounded-md bg-brand-500 text-white font-bold text-xs shadow-2xs">
            <span>स</span>
          </div>
          <div className="flex items-center gap-2 text-xs">
            <span className="font-semibold text-brand-900">
              Opening Saath Family Khata
            </span>
            <span className="text-brand-600/60">•</span>
            <span className="text-brand-700 font-medium">
              खाते उघडत आहे…
            </span>
          </div>
        </div>

        {/* Delicate indeterminate progress line */}
        <div className="w-36 h-1.5 bg-brand-100 rounded-full overflow-hidden">
          <div className="h-full bg-brand-500 rounded-full w-1/2 animate-[shimmer-warm_1.2s_infinite_ease-in-out]" />
        </div>
      </div>

      {/* 2. Financial Commitment Runway Bar Skeleton */}
      <div className="bg-khata-canvas px-6 py-3 border-b border-khata-subtle">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 max-w-5xl">
          {/* Card 1: Parents' Bills */}
          <div className="rounded-xl border border-khata-subtle bg-white/70 p-3.5 space-y-2.5 shadow-2xs">
            <div className="flex items-center justify-between">
              <div className="h-3.5 w-40 skeleton-warm rounded-md" />
              <div className="h-4 w-16 skeleton-warm rounded-md" />
            </div>
            <div className="flex items-baseline gap-2">
              <div className="h-7 w-28 skeleton-warm rounded-lg" />
              <div className="h-3 w-20 skeleton-warm rounded-md" />
            </div>
            <div className="flex gap-2 pt-1">
              <div className="h-5 w-24 skeleton-warm rounded-md" />
              <div className="h-5 w-20 skeleton-warm rounded-md" />
              <div className="h-5 w-16 skeleton-warm rounded-md" />
            </div>
          </div>

          {/* Card 2: Earner's EMIs */}
          <div className="rounded-xl border border-khata-subtle bg-white/70 p-3.5 space-y-2.5 shadow-2xs">
            <div className="flex items-center justify-between">
              <div className="h-3.5 w-40 skeleton-warm rounded-md" />
              <div className="h-4 w-16 skeleton-warm rounded-md" />
            </div>
            <div className="flex items-baseline gap-2">
              <div className="h-7 w-28 skeleton-warm rounded-lg" />
              <div className="h-3 w-20 skeleton-warm rounded-md" />
            </div>
            <div className="flex gap-2 pt-1">
              <div className="h-5 w-28 skeleton-warm rounded-md" />
              <div className="h-5 w-20 skeleton-warm rounded-md" />
            </div>
          </div>
        </div>
      </div>

      {/* 3. Action Toolbar Skeleton */}
      <div className="bg-khata-raised/80 border-b border-khata-subtle px-6 py-2.5 flex items-center justify-between gap-3 shadow-2xs">
        <div className="flex items-center gap-4">
          {/* Tabs skeleton */}
          <div className="flex items-center gap-1 bg-white border border-khata-subtle p-1 rounded-xl">
            <div className="h-6 w-20 skeleton-warm rounded-md" />
            <div className="h-6 w-20 skeleton-warm rounded-md" />
          </div>
          {/* Members presence skeleton */}
          <div className="hidden sm:flex items-center gap-2">
            {[1, 2, 3, 4, 5].map((i) => (
              <div key={i} className="flex items-center gap-1.5 px-2 py-1 rounded-lg border border-khata-subtle bg-white">
                <div className="w-5 h-5 rounded-full skeleton-warm" />
                <div className="h-3 w-12 skeleton-warm rounded" />
              </div>
            ))}
          </div>
        </div>

        {/* Toolbar buttons skeleton */}
        <div className="flex items-center gap-2">
          <div className="h-8 w-28 skeleton-warm rounded-lg" />
          <div className="h-8 w-32 skeleton-warm rounded-lg" />
          <div className="h-8 w-20 skeleton-warm rounded-lg" />
        </div>
      </div>

      {/* 4. Kanban Columns Skeleton */}
      <div className="flex flex-1 gap-4 p-6 overflow-hidden">
        {[
          { title: "01 NEW & ESCALATED", rail: "border-l-brand-500", cards: 2 },
          { title: "02 NEEDS REVIEW", rail: "border-l-ochre-500", cards: 1 },
          { title: "03 CLAIMED", rail: "border-l-blue-600", cards: 2 },
          { title: "04 SETTLED / DONE", rail: "border-l-sage-600", cards: 2 },
        ].map((col, idx) => (
          <div
            key={idx}
            className="flex flex-col rounded-xl border border-khata-subtle bg-khata-raised/40 min-w-[300px] w-[300px] p-3 shadow-2xs"
          >
            {/* Column header skeleton */}
            <div className="flex items-center justify-between pb-2.5 mb-2.5 border-b border-khata-subtle/80 px-1">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full skeleton-warm" />
                <span className="font-mono text-[10px] font-bold text-khata-muted tracking-wider">
                  {col.title}
                </span>
              </div>
              <div className="w-5 h-4 skeleton-warm rounded" />
            </div>

            {/* Task Card Skeletons */}
            <div className="flex flex-col gap-2.5 flex-1">
              {Array.from({ length: col.cards }).map((_, cIdx) => (
                <div
                  key={cIdx}
                  className={`bg-white rounded-xl border border-khata-subtle p-3.5 shadow-2xs space-y-3 border-l-3 ${col.rail}`}
                >
                  <div className="flex items-center justify-between">
                    <div className="h-4 w-20 skeleton-warm rounded" />
                    <div className="h-4 w-12 skeleton-warm rounded-md" />
                  </div>
                  <div className="h-4 w-3/4 skeleton-warm rounded" />
                  <div className="flex items-center justify-between pt-1 border-t border-khata-subtle/50">
                    <div className="h-3 w-16 skeleton-warm rounded" />
                    <div className="w-5 h-5 rounded-full skeleton-warm" />
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

