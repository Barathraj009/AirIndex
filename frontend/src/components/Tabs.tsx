export interface TabItem {
  key: string
  label: string
}

export function TabBar({ tabs, active, onChange }: { tabs: TabItem[]; active: string; onChange: (key: string) => void }) {
  return (
    <div
      role="tablist"
      aria-label="Page sections"
      className="mb-6 flex flex-wrap gap-1.5 rounded-xl border border-line bg-surface p-1.5 shadow-card"
    >
      {tabs.map((t) => {
        const selected = active === t.key
        return (
          <button
            key={t.key}
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(t.key)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-all ${
              selected
                ? 'bg-brand-500/10 text-brand-700 shadow-[inset_0_0_0_1px_rgba(20,113,232,0.2)]'
                : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
            }`}
          >
            {t.label}
          </button>
        )
      })}
    </div>
  )
}