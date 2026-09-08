(function () {
  const { useState } = React;
  const { useDashboard } = window.__SHAPE__.dashboardContext;
  const { signalLabel, signalColor, signalRank } = window.__SHAPE__.dashboardUtils;

  // Three-segment strip showing the actual T+1/T+2/T+3 direction (red=up, green=down).
  function PerfBar({ entry }) {
    if (!entry || !entry.rating) {
      return <div className="perf-bar-stack" style={{ marginTop: '4px' }}></div>;
    }
    const segs = [entry.ret1, entry.ret2, entry.ret3].map((ret, i) => {
      const cls = ret === null || ret === undefined ? '' : ret >= 0 ? 'up' : 'down';
      return <div key={i} className={`perf-bar-seg ${cls}`}></div>;
    });
    return <div className="perf-bar-stack" style={{ marginTop: '4px' }}>{segs}</div>;
  }

  // Letter badge for the five-level rating: B / OW- / H / UW- / S (rank drives the glyph).
  function ratingLetter(rating) {
    const map = {
      Buy: 'B', BUY: 'B',
      Overweight: 'OW', OVERWEIGHT: 'OW',
      Hold: 'H', HOLD: 'H',
      Underweight: 'UW', UNDERWEIGHT: 'UW',
      Sell: 'S', SELL: 'S',
    };
    return map[rating] || '·';
  }

  function StatRow({ rows }) {
    let correct = 0;
    let wrong = 0;
    let none = 0;
    rows.forEach((e) => {
      if (!e.rating) { none++; return; }
      const rank = signalRank(e.rating);
      // Judge by T+1 direction vs the rating direction: bullish ratings expect a rise.
      if (e.ret1 === null || e.ret1 === undefined) { none++; return; }
      if (rank > 0 && e.ret1 > 0) correct++;
      else if (rank < 0 && e.ret1 < 0) correct++;
      else if (rank === 0) { if (Math.abs(e.ret1) < 1.5) correct++; else wrong++; }
      else wrong++;
    });
    const active = rows.length - none;
    const acc = active ? (correct / active) * 100 : 0;
    return (
      <div className="matrix-stats">
        <span style={{ color: 'var(--red)' }}>✓ {correct}</span>
        <span style={{ color: 'var(--green)' }}>✗ {wrong}</span>
        <span style={{ color: 'var(--accent)' }}>{acc.toFixed(0)}%</span>
      </div>
    );
  }

  function PerformanceMatrix() {
    const { holdings, tradingDays, matrix, activeHoldingIdx, setActiveHoldingIdx } = useDashboard();
    const [tip, setTip] = useState(null);

    const handleHover = (stock, day, entry, el) => {
      const rect = el.getBoundingClientRect();
      const containerRect = document.getElementById('matrix-container')?.getBoundingClientRect();
      if (!containerRect) return;
      setTip({
        stock,
        day,
        entry,
        x: rect.left - containerRect.left + rect.width / 2,
        y: rect.top - containerRect.top - 8,
      });
    };

    const fmtPct = (v) => (v === null || v === undefined ? null : `${v >= 0 ? '+' : ''}${v.toFixed(2)}%`);

    // Jump to the report detail page for the clicked cell's date.
    const openReport = (stock, entry) => {
      if (!entry || !entry.reportDir || !stock.ticker) return;
      window.open(
        '/reports#ticker=' + encodeURIComponent(stock.ticker) + '&date=' + encodeURIComponent(entry.reportDir),
        '_blank'
      );
    };

    const currentTip = tip ? (
      <div
        className="matrix-tooltip"
        style={{ left: tip.x, top: tip.y, transform: 'translate(-50%, -100%)' }}
      >
        <div className="matrix-tooltip-header">
          <span>{tip.stock.name} ({tip.stock.code})</span>
          <span>{tip.day.fullDate || tip.day.date}</span>
        </div>
        {tip.entry.rating ? (
          <>
            <div className="matrix-tooltip-signal">
              信号：
              <span
                className={`matrix-tooltip-badge ${signalColor(tip.entry.rating)}`}
              >
                {tip.entry.rating} · {signalLabel(tip.entry.rating)}
              </span>
            </div>
            <div className="matrix-tooltip-ret matrix-tooltip-ret-head">
              <span></span>
              <span>日涨跌</span>
              <span>累计</span>
            </div>
            {[
              ['T+1', tip.entry.ret1, tip.entry.cum1],
              ['T+2', tip.entry.ret2, tip.entry.cum2],
              ['T+3', tip.entry.ret3, tip.entry.cum3],
              ['T+7', tip.entry.ret7, tip.entry.cum7],
              ['至今', tip.entry.retLatest, tip.entry.cumLatest],
            ].map(([label, ret, cum]) => (
              <div className="matrix-tooltip-ret" key={label}>
                <span className="ret-label">{label}</span>
                <span style={{ color: fmtPct(ret) ? (ret >= 0 ? 'var(--red)' : 'var(--green)') : 'var(--text-secondary)' }}>
                  {fmtPct(ret) || '无数据'}
                </span>
                <span style={{ color: fmtPct(cum) ? (cum >= 0 ? 'var(--red)' : 'var(--green)') : 'var(--text-secondary)' }}>
                  {fmtPct(cum) || '无数据'}
                </span>
              </div>
            ))}
          </>
        ) : (
          <div className="matrix-tooltip-empty">当日无系统信号</div>
        )}
      </div>
    ) : null;

    return (
      <section className="card performance-section" id="matrix-container">
        <div className="card-title">
          <span>近 15 个交易日静态回测快照</span>
          <span className="subtitle">悬停查看详情 · 点击股票行切换选中</span>
        </div>

        <div className="matrix-legend">
          <div className="matrix-legend-item"><span className="legend-dot" style={{ background: '#dc2626' }}></span>买入</div>
          <div className="matrix-legend-item"><span className="legend-dot" style={{ background: '#ef4444' }}></span>增持</div>
          <div className="matrix-legend-item"><span className="legend-dot" style={{ background: '#ca8a04' }}></span>持有</div>
          <div className="matrix-legend-item"><span className="legend-dot" style={{ background: '#22c55e' }}></span>减持</div>
          <div className="matrix-legend-item"><span className="legend-dot" style={{ background: '#16a34a' }}></span>卖出</div>
          <div className="matrix-legend-item"><span className="legend-dot" style={{ background: 'var(--border)' }}></span>无信号</div>
        </div>

        <div className="matrix-scroll">
          <table className="matrix-table">
            <thead>
              <tr>
                <th className="matrix-th-stock">
                  <div>日期 →</div>
                  <div className="matrix-th-sub">股票 ↓</div>
                </th>
                {tradingDays.map((d, i) => (
                  <th key={i} className="matrix-th-day">
                    <div>{d.date.split('-')[1]}</div>
                    <div className="matrix-th-sub">星期{d.dow}</div>
                  </th>
                ))}
                <th className="matrix-th-hit">15日命中</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((s, idx) => {
                const rowData = matrix[s.code] || [];
                const isActive = idx === activeHoldingIdx;
                return (
                  <tr key={s.code} className={isActive ? 'matrix-row-active' : ''}>
                    <td
                      className="matrix-td-stock"
                      onClick={() => setActiveHoldingIdx(idx)}
                    >
                      <div className="matrix-stock-name">{s.name}</div>
                      <div className="matrix-stock-code">{s.code}</div>
                    </td>
                    {rowData.map((e, i) => {
                      const letter = e.rating ? ratingLetter(e.rating) : '·';
                      const clickable = !!e.reportDir && !!s.ticker;
                      return (
                        <td key={i} className="matrix-td-cell">
                          <div
                            className={`matrix-cell ${e.rating ? signalColor(e.rating) : 'empty'}${clickable ? ' clickable' : ''}`}
                            onMouseEnter={(ev) => handleHover(s, tradingDays[i] || e, e, ev.currentTarget)}
                            onMouseLeave={() => setTip(null)}
                            onClick={() => openReport(s, e)}
                            title={clickable ? '点击查看报告详情' : undefined}
                          >
                            {letter}
                          </div>
                          <PerfBar entry={e} />
                        </td>
                      );
                    })}
                    <td className="matrix-td-hit">
                      <StatRow rows={rowData} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <div className="matrix-footer">
          <span>底部三格色条：信号后 1/2/3 日实际涨跌（红涨 绿跌 灰无数据）· 悬停查看 T+1/T+2/T+3/T+7/至今涨跌与累计</span>
        </div>

        {currentTip}
      </section>
    );
  }

  window.__SHAPE__.dashboardPerformanceMatrix = PerformanceMatrix;
})();
