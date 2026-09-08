(function () {
  const { useApp } = window.__SHAPE__.context;
  const { signalColor, signalLabel } = window.__SHAPE__.utils;

  function PerfBar({ t1, t2, signal }) {
    // Determine perf-bar colour: signal correctness
    // BUY -> success if t1 > 0; SELL -> success if t1 < 0; HOLD -> success if |t1| < 0.8
    if (!signal) {
      return <div className="perf-bar w-full mt-1" style={{ background: '#2a3630' }}></div>;
    }
    let correct = false;
    if (signal === 'BUY') correct = t1 > 0;
    else if (signal === 'SELL') correct = t1 < 0;
    else correct = Math.abs(t1) < 0.8;
    const color = correct ? '#dc2626' : '#16a34a';
    return (
      <div className="flex gap-[1px] mt-1">
        <div className="perf-bar flex-1" style={{ background: color, opacity: 0.9 }}></div>
        <div className="perf-bar flex-1" style={{ background: color, opacity: 0.6 }}></div>
        <div className="perf-bar flex-1" style={{ background: color, opacity: 0.35 }}></div>
      </div>
    );
  }

  function MatrixCell({ entry, code, dayIdx, isActive, onHover, onLeave }) {
    const sig = entry.signal;
    const cls = signalColor(sig);
    const label = { BUY: '🔴', SELL: '🟢', HOLD: '🟡', null: '' }[sig] || '';
    const letter = sig ? sig[0] : '·';
    const isEmpty = !sig;

    return (
      <div
        className={`letterpress-tile ${cls} h-8 flex items-center justify-center cursor-pointer relative`}
        onMouseEnter={(e) => onHover(code, dayIdx, entry, e.currentTarget)}
        onMouseLeave={onLeave}
        title=""
      >
        {!isEmpty && (
          <span
            className="font-mono-num text-[11px] font-semibold tracking-wider"
            style={{ textShadow: '0 1px 0 rgba(0,0,0,0.35)' }}
          >
            {letter}
          </span>
        )}
        {isEmpty && (
          <span className="text-[10px]" style={{ color: '#3d4a44' }}>·</span>
        )}
      </div>
    );
  }

  function StatRow({ label, rows }) {
    const total = rows.length;
    const stats = rows.reduce((acc, e) => {
      if (!e.signal) acc.none++;
      else if (e.signal === 'BUY' && e.t1 > 0) acc.correct++;
      else if (e.signal === 'SELL' && e.t1 < 0) acc.correct++;
      else if (e.signal === 'HOLD' && Math.abs(e.t1) < 0.8) acc.correct++;
      else acc.wrong++;
      return acc;
    }, { correct: 0, wrong: 0, none: 0 });
    const active = total - stats.none;
    const acc = active ? (stats.correct / active) * 100 : 0;
    return (
      <div className="grid grid-cols-3 gap-1 text-[9px] font-mono-num">
        <div className="text-red-400">✓ {stats.correct}</div>
        <div className="text-emerald-400">✗ {stats.wrong}</div>
        <div className="text-primary">{acc.toFixed(0)}%</div>
      </div>
    );
  }

  function PerformanceMatrix() {
    const { stocks, activeCode, setActiveCode, activeDateIdx, setActiveDateIdx } = useApp();
    const { MATRIX, TRADING_DAYS, getReport } = window.__SHAPE__.mocks;
    const [tip, setTip] = React.useState(null);
    // activeDateIdx=0 is the latest-day snapshot (not in matrix); matrix col highlight only when idx>=1
    const highlightCol = activeDateIdx > 0 ? activeDateIdx - 1 : -1;

    const handleHover = (code, dayIdx, entry, el) => {
      const rect = el.getBoundingClientRect();
      const parent = el.offsetParent && el.offsetParent.getBoundingClientRect();
      const containerRect = document.getElementById('matrix-container')?.getBoundingClientRect();
      if (!containerRect) return;
      setTip({
        code,
        dayIdx,
        entry,
        x: rect.left - containerRect.left + rect.width / 2,
        y: rect.top - containerRect.top - 8,
      });
    };
    const handleLeave = () => setTip(null);

    const currentTip = tip ? (() => {
      const stock = stocks.find(s => s.code === tip.code) || { name: tip.code };
      const day = TRADING_DAYS[tip.dayIdx];
      return { stock, day, entry: tip.entry, x: tip.x, y: tip.y };
    })() : null;

    return (
      <section className="panel relative overflow-visible" id="matrix-container">
        <header className="px-5 pt-4 pb-3 border-b border-brand-border flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="tab-serif text-primary">Performance Foundry · 铸字回测盘</span>
              {highlightCol >= 0 && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 border border-primary/60 text-primary tab-serif text-[9px]" style={{ letterSpacing: '0.15em' }}>
                  <span className="w-1.5 h-1.5 rounded-full bg-primary pulse-dot"></span>
                  当前视角 · 2026-{TRADING_DAYS[highlightCol].date} · T-{highlightCol + 1}
                </span>
              )}
            </div>
            <h2 className="font-display text-2xl text-base-content leading-tight">
              📊 历史信号绩效追踪矩阵
            </h2>
            <p className="text-[11px] text-brand-muted mt-1.5 leading-relaxed max-w-2xl">
              近 15 个交易日静态回测快照,<span className="text-primary">单击列头</span>直接跳转到当日视角,悬停方块查看凸版详情。
            </p>
          </div>

          <div className="flex items-center gap-4 text-[10px] font-mono-num">
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 signal-buy inline-block"></span>
              <span className="text-brand-muted">🔴 买入</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 signal-sell inline-block"></span>
              <span className="text-brand-muted">🟢 卖出</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 signal-hold inline-block"></span>
              <span className="text-brand-muted">🟡 持有</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="w-3 h-3 signal-none inline-block"></span>
              <span className="text-brand-muted">无信号</span>
            </div>
          </div>
        </header>

        <div className="p-4 overflow-x-auto scroll-thin">
          <table className="w-full border-separate" style={{ borderSpacing: '3px 3px', minWidth: '900px' }}>
            <thead>
              <tr>
                <th className="text-left align-bottom w-[168px] pr-2">
                  <div className="tab-serif text-brand-muted">日期 →</div>
                  <div className="text-[9px] text-brand-muted font-mono-num mt-0.5">股票 ↓</div>
                </th>
                {TRADING_DAYS.map((d, i) => {
                  const isCurrent = i === highlightCol;
                  return (
                    <th key={i} className="text-center align-bottom pb-1">
                      <button
                        type="button"
                        onClick={() => setActiveDateIdx(i + 1)}
                        className={`w-full py-0.5 transition ${isCurrent ? 'bg-primary/20 border-b-2 border-primary' : 'hover:bg-base-300/40 border-b-2 border-transparent'}`}
                        title={`跳转到 2026-${d.date}`}
                      >
                        <div className={`font-mono-num text-[10px] leading-tight ${isCurrent ? 'text-primary' : 'text-base-content'}`}>{d.date.split('-')[1]}</div>
                        <div className={`tab-serif text-[8px] ${isCurrent ? 'text-primary' : 'text-brand-muted'}`}>星期{d.dow}</div>
                      </button>
                    </th>
                  );
                })}
                <th className="text-center align-bottom pl-2 pb-1 min-w-[80px]">
                  <div className="tab-serif text-primary">15日 命中</div>
                </th>
              </tr>
            </thead>
            <tbody>
              {stocks.map(s => {
                const rowData = MATRIX[s.code] || [];
                const isActive = s.code === activeCode;
                return (
                  <tr key={s.code} className={isActive ? 'bg-primary/5' : ''}>
                    <td
                      className="px-2 py-1 cursor-pointer"
                      onClick={() => setActiveCode(s.code)}
                    >
                      <div className="flex flex-col">
                        <span className={`font-serif-body text-[13px] leading-tight ${isActive ? 'text-primary' : 'text-base-content'}`}>
                          {s.name}
                        </span>
                        <span className="font-mono-num text-[9px] text-brand-muted">{s.code}</span>
                      </div>
                    </td>
                    {rowData.map((e, i) => {
                      const isCurrent = i === highlightCol;
                      return (
                        <td key={i} className={`p-0 relative ${isCurrent ? 'ring-1 ring-primary/60 shadow-[0_0_12px_rgba(212,163,115,0.25)]' : ''}`}>
                          <MatrixCell
                            entry={e}
                            code={s.code}
                            dayIdx={i}
                            onHover={handleHover}
                            onLeave={handleLeave}
                          />
                          <PerfBar t1={e.t1} t2={e.t2} signal={e.signal} />
                        </td>
                      );
                    })}
                    <td className="px-2 py-1 border-l border-brand-border/60">
                      <StatRow label={s.name} rows={rowData} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <footer className="px-5 py-3 border-t border-brand-border bg-base-300/30">
          <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-[10px] text-brand-muted font-mono-num">
            <span className="tab-serif text-primary">底部三色绩效条</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-1 bg-red-500 inline-block"></span>信号命中(上涨)</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-1 bg-emerald-500 inline-block"></span>信号未中(下跌)</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-1 inline-block" style={{ background: '#2a3630' }}></span>无数据</span>
          </div>
        </footer>

        {/* tooltip */}
        {currentTip && (
          <div
            className="tooltip-card paper grain"
            style={{
              left: `${currentTip.x}px`,
              top: `${currentTip.y}px`,
              transform: 'translate(-50%, -100%)',
              minWidth: '280px',
              padding: '14px 16px',
            }}
          >
            <div className="flex items-baseline justify-between border-b pb-2 mb-2" style={{ borderColor: '#c8b590' }}>
              <div>
                <div className="tab-serif" style={{ color: '#8b6c3f' }}>凸版拓印 · Hover Print</div>
                <div className="font-display text-lg mt-0.5" style={{ color: '#1a1912' }}>
                  📌 {currentTip.stock.name} <span className="text-xs" style={{ color: '#8b6c3f' }}>({currentTip.stock.code})</span>
                </div>
              </div>
              <div className="font-mono-num text-[11px]" style={{ color: '#8b6c3f' }}>2026-{currentTip.day.date}</div>
            </div>

            {currentTip.entry.signal ? (
              <>
                <div className="flex items-center gap-2 mb-2">
                  <span className="tab-serif text-[10px]" style={{ color: '#8b6c3f' }}>触发信号:</span>
                  <span
                    className="tab-serif px-2 py-0.5 text-[10px]"
                    style={{
                      background: currentTip.entry.signal === 'BUY' ? '#dc2626' : currentTip.entry.signal === 'SELL' ? '#16a34a' : '#ca8a04',
                      color: currentTip.entry.signal === 'HOLD' ? '#1a1912' : '#fff',
                    }}
                  >
                    {currentTip.entry.signal} · {signalLabel(currentTip.entry.signal)}
                  </span>
                </div>
                <div className="text-[11px] font-serif-body mb-2" style={{ color: '#1a1912' }}>
                  📅 信号后表现(1-3日实际涨跌):
                </div>
                <div className="space-y-1 font-mono-num text-[11px]" style={{ color: '#1a1912' }}>
                  <div className="flex items-center justify-between">
                    <span>• T+1 日:</span>
                    <span style={{ color: currentTip.entry.t1 >= 0 ? '#dc2626' : '#16a34a' }}>
                      {currentTip.entry.t1 >= 0 ? '+' : ''}{currentTip.entry.t1.toFixed(2)}% (累计 {currentTip.entry.t1 >= 0 ? '+' : ''}{currentTip.entry.t1.toFixed(2)}%)
                      <span className="ml-1">{currentTip.entry.t1 >= 0 ? '🟥' : '🟩'}</span>
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span>• T+2 日:</span>
                    <span style={{ color: currentTip.entry.t2 >= 0 ? '#dc2626' : '#16a34a' }}>
                      {currentTip.entry.t2 >= 0 ? '+' : ''}{currentTip.entry.t2.toFixed(2)}% (累计 {currentTip.entry.t2 >= 0 ? '+' : ''}{currentTip.entry.t2.toFixed(2)}%)
                      <span className="ml-1">{currentTip.entry.t2 >= 0 ? '🟥' : '🟩'}</span>
                    </span>
                  </div>
                </div>
                <div className="mt-3 pt-2 text-[10px] italic" style={{ borderTop: '1px dashed #c8b590', color: '#8b6c3f' }}>
                  双击方块可反向穿透查看当天完整 Markdown 报告 →
                </div>
              </>
            ) : (
              <div className="text-[11px] font-serif-body" style={{ color: '#8b6c3f' }}>
                当日无系统信号,休市或数据缺失。
              </div>
            )}
          </div>
        )}
      </section>
    );
  }

  window.__SHAPE__.PerformanceMatrix = PerformanceMatrix;
})();
