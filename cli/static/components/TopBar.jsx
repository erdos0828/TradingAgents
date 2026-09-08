(function () {
  const { useApp } = window.__SHAPE__.context;

  function DateSwitcher() {
    const {
      dates, activeDateIdx, activeDate,
      prevDate, nextDate, jumpLatest, setActiveDateIdx,
    } = useApp();
    const [open, setOpen] = React.useState(false);

    const canGoOlder = activeDateIdx < dates.length - 1;
    const canGoNewer = activeDateIdx > 0;
    const isLatest = activeDateIdx === 0;

    return (
      <div className="relative flex items-stretch border border-brand-border">
        <button
          type="button"
          onClick={prevDate}
          disabled={!canGoOlder}
          className="px-2.5 border-r border-brand-border text-brand-muted hover:text-primary hover:bg-base-300 disabled:opacity-30 disabled:cursor-not-allowed transition tab-serif"
          title="前一交易日"
        >
          ◀
        </button>

        <button
          type="button"
          onClick={() => setOpen(o => !o)}
          className="px-4 py-1.5 min-w-[190px] flex flex-col items-center hover:bg-base-300/50 transition"
        >
          <div className="flex items-center gap-2 leading-tight">
            <span className="font-mono-num text-base text-base-content">{activeDate.date}</span>
            <span className="tab-serif text-primary">星期{activeDate.dow}</span>
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            {isLatest ? (
              <span className="inline-flex items-center gap-1 text-[9px] tab-serif text-emerald-400" style={{ letterSpacing: '0.15em' }}>
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 pulse-dot"></span>
                LATEST · 收盘结账
              </span>
            ) : (
              <span className="text-[9px] tab-serif text-amber-400" style={{ letterSpacing: '0.15em' }}>
                T-{activeDateIdx} · 历史回放
              </span>
            )}
          </div>
        </button>

        <button
          type="button"
          onClick={nextDate}
          disabled={!canGoNewer}
          className="px-2.5 border-l border-brand-border text-brand-muted hover:text-primary hover:bg-base-300 disabled:opacity-30 disabled:cursor-not-allowed transition tab-serif"
          title="后一交易日"
        >
          ▶
        </button>

        {!isLatest && (
          <button
            type="button"
            onClick={jumpLatest}
            className="px-3 border-l border-brand-border tab-serif text-primary hover:bg-primary hover:text-primary-content transition"
            title="回到最新交易日"
          >
            ⟲ 最新
          </button>
        )}

        {open && (
          <div
            className="absolute right-0 top-full mt-1 z-40 panel min-w-[240px] max-h-[380px] overflow-y-auto scroll-thin"
            onMouseLeave={() => setOpen(false)}
          >
            <div className="px-3 py-2 border-b border-brand-border tab-serif text-primary flex items-center justify-between">
              <span>选择交易日</span>
              <span className="text-[9px] text-brand-muted font-mono-num">{dates.length} 天</span>
            </div>
            {dates.map((d, i) => (
              <button
                key={d.date}
                type="button"
                onClick={() => { setActiveDateIdx(i); setOpen(false); }}
                className={`w-full px-3 py-2 flex items-center justify-between border-b border-brand-border/40 hover:bg-primary/10 transition ${i === activeDateIdx ? 'bg-primary/20' : ''}`}
              >
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${i === activeDateIdx ? 'bg-primary' : 'bg-brand-border'}`}></span>
                  <span className={`font-mono-num text-[13px] ${i === activeDateIdx ? 'text-primary' : 'text-base-content'}`}>{d.date}</span>
                  <span className="tab-serif text-brand-muted">周{d.dow}</span>
                </div>
                {d.isLatest ? (
                  <span className="tab-serif text-emerald-400 text-[9px]" style={{ letterSpacing: '0.15em' }}>LATEST</span>
                ) : (
                  <span className="tab-serif text-brand-muted text-[9px]" style={{ letterSpacing: '0.15em' }}>T-{i}</span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  function TopBar() {
    const { market, setMarket, activeDate } = useApp();

    return (
      <header className="border-b-2 border-brand-border bg-gradient-to-b from-base-200 to-base-100 relative">
        {/* newsroom top rule */}
        <div className="rule-double"></div>

        <div className="px-6 py-4 flex flex-wrap items-center justify-between gap-4">
          {/* masthead */}
          <div className="flex items-center gap-5">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 border-2 border-primary flex items-center justify-center relative">
                <span className="font-display text-2xl text-primary leading-none">智</span>
                <span className="absolute -top-1 -right-1 w-2 h-2 bg-primary pulse-dot"></span>
              </div>
              <div>
                <div className="tab-serif text-primary">Ticker Foundry · 铸字行情台</div>
                <h1 className="font-display text-3xl text-base-content leading-none mt-1">
                  💡 智投工作台 <span className="italic text-primary text-xl">v3.0</span>
                </h1>
              </div>
            </div>

            <div className="hidden lg:flex flex-col text-[10px] font-mono-num text-brand-muted tracking-wider ml-4 pl-5 border-l border-brand-border">
              <span>Issue · <span className="text-base-content">{activeDate.date}</span></span>
              <span>Vol. XXVIII · No. 249</span>
              <span>Editor · 智投研究所</span>
            </div>
          </div>

          {/* right controls */}
          <div className="flex items-center gap-5">
            {/* market switch */}
            <div className="flex items-stretch border border-brand-border">
              <button
                type="button"
                onClick={() => setMarket('A')}
                className={`px-4 py-2 flex items-center gap-2 tab-serif transition ${market === 'A' ? 'bg-red-600/90 text-white' : 'text-brand-muted hover:bg-base-300'}`}
              >
                <span className="w-2 h-2 rounded-full bg-red-500"></span>
                A 股市场
              </button>
              <button
                type="button"
                onClick={() => setMarket('US')}
                className={`px-4 py-2 flex items-center gap-2 tab-serif transition ${market === 'US' ? 'bg-primary text-primary-content' : 'text-brand-muted hover:bg-base-300'}`}
              >
                <span className="w-2 h-2 rounded-full bg-white/70"></span>
                美股市场
              </button>
            </div>

            <DateSwitcher />

            <div className="hidden xl:flex items-center gap-4 text-[10px] font-mono-num text-brand-muted">
              <div className="h-8 w-px bg-brand-border"></div>
              <div className="flex flex-col items-end">
                <span>Uptime · 99.98%</span>
                <span className="text-emerald-400">◉ Streams OK</span>
              </div>
            </div>

            <div className="w-8 h-8 rounded-full border border-brand-border bg-primary/20 flex items-center justify-center font-mono-num text-primary text-[13px]">
              M
            </div>
          </div>
        </div>

        <div className="rule-thick"></div>
      </header>
    );
  }

  window.__SHAPE__.TopBar = TopBar;
})();
