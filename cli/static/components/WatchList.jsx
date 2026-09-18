(function () {
  const { useApp } = window.__SHAPE__.context;
  const { fmtNum, fmtPct } = window.__SHAPE__.utils;

  function SignalDot({ signal }) {
    const cfg = {
      BUY: { color: '#ef4444', label: 'B' },
      SELL: { color: '#22c55e', label: 'S' },
      HOLD: { color: '#eab308', label: 'H' },
    };
    const c = cfg[signal] || { color: '#4a5750', label: '·' };
    return (
      <span
        className="inline-flex items-center justify-center w-4 h-4 text-[9px] font-mono-num font-semibold"
        style={{
          background: c.color,
          color: signal === 'HOLD' ? '#1a1912' : '#fff',
          borderRadius: '1px',
          lineHeight: 1,
        }}
      >
        {c.label}
      </span>
    );
  }

  function WatchList() {
    const { stocks, activeCode, setActiveCode, market, activeDate, activeDateIdx } = useApp();

    const currencySymbol = market === 'A' ? '¥' : '$';

    return (
      <section className="panel h-full flex flex-col">
        {/* header */}
        <header className="px-4 pt-4 pb-3 border-b border-brand-border">
          <div className="flex items-baseline justify-between mb-1">
            <span className="tab-serif text-primary">Watchlist</span>
            <span className="font-mono-num text-[10px] text-brand-muted">
              {stocks.length} 只 · {currencySymbol}
            </span>
          </div>
          <h2 className="font-display text-2xl leading-tight text-base-content">
            我的<span className="italic">静态</span>清单
          </h2>
          <p className="text-[11px] text-brand-muted mt-1 leading-relaxed">
            数据截止 <span className="font-mono-num text-primary">{activeDate.date}</span> 收盘
            {activeDateIdx > 0 && (
              <span className="ml-1.5 text-amber-400">· 历史 T-{activeDateIdx}</span>
            )}
          </p>
        </header>

        {/* column headers */}
        <div className="px-4 py-2 border-b border-brand-border/60 divider-hatch">
          <div className="grid grid-cols-[1fr_auto_auto] gap-2 text-[10px] uppercase tracking-[0.15em] text-brand-muted font-mono-num">
            <span>代码 / 名称</span>
            <span className="text-right">昨收</span>
            <span className="text-right w-14">日涨跌</span>
          </div>
        </div>

        {/* rows */}
        <div className="flex-1 overflow-y-auto scroll-thin">
          {stocks.map((s, idx) => {
            const isActive = s.code === activeCode;
            const isUp = s.changePct >= 0;
            return (
              <button
                key={s.code}
                type="button"
                onClick={() => setActiveCode(s.code)}
                className={`stock-row w-full text-left px-4 py-3 border-b border-brand-border/40 grid grid-cols-[1fr_auto_auto] gap-2 items-center ${isActive ? 'active' : ''}`}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <SignalDot signal={s.signal} />
                    <span className="font-mono-num text-[11px] text-brand-muted">{s.code}</span>
                  </div>
                  <div className="font-serif-body text-[15px] text-base-content truncate mt-0.5">
                    {s.name}
                  </div>
                </div>
                <div className="font-mono-num text-[13px] text-base-content text-right whitespace-nowrap">
                  {fmtNum(s.prev)}
                </div>
                <div className={`font-mono-num text-[12px] text-right w-14 ${isUp ? 'text-red-400' : 'text-emerald-400'}`}>
                  {fmtPct(s.changePct)}
                </div>
              </button>
            );
          })}
        </div>

        {/* footer hint */}
        <footer className="px-4 py-3 border-t border-brand-border bg-base-300/40">
          <p className="text-[10px] text-brand-muted leading-relaxed">
            <span className="text-primary">›</span> 单击股票将联动右侧走势、分析仪表盘、深度报告与底部矩阵。
          </p>
        </footer>
      </section>
    );
  }

  window.__SHAPE__.WatchList = WatchList;
})();
