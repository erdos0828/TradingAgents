(function () {
  const { useState } = React;
  const { useDashboard } = window.__SHAPE__.dashboardContext;
  const { signalLabel, signalColor } = window.__SHAPE__.dashboardUtils;

  function PerfBar({ t1, signal }) {
    if (!signal) {
      return <div className="perf-bar" style={{ background: 'var(--border)', marginTop: '4px' }}></div>;
    }
    let correct = false;
    if (signal === 'BUY') correct = t1 > 0;
    else if (signal === 'SELL') correct = t1 < 0;
    else correct = Math.abs(t1) < 0.8;
    const color = correct ? 'var(--red)' : 'var(--green)';
    return (
      <div className="perf-bar-stack" style={{ marginTop: '4px' }}>
        <div className="perf-bar-seg" style={{ background: color, opacity: 0.9 }}></div>
        <div className="perf-bar-seg" style={{ background: color, opacity: 0.6 }}></div>
        <div className="perf-bar-seg" style={{ background: color, opacity: 0.35 }}></div>
      </div>
    );
  }

  function StatRow({ rows }) {
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
      <div className="matrix-stats">
        <span style={{ color: 'var(--red)' }}>✓ {stats.correct}</span>
        <span style={{ color: 'var(--green)' }}>✗ {stats.wrong}</span>
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

    const currentTip = tip ? (
      <div
        className="matrix-tooltip"
        style={{ left: tip.x, top: tip.y, transform: 'translate(-50%, -100%)' }}
      >
        <div className="matrix-tooltip-header">
          <span>{tip.stock.name} ({tip.stock.code})</span>
          <span>2026-{tip.day.date}</span>
        </div>
        {tip.entry.signal ? (
          <>
            <div className="matrix-tooltip-signal">
              信号：
              <span
                className={`matrix-tooltip-badge ${signalColor(tip.entry.signal)}`}
              >
                {tip.entry.signal} · {signalLabel(tip.entry.signal)}
              </span>
            </div>
            <div className="matrix-tooltip-row">
              <span>T+1 日涨跌</span>
              <span style={{ color: tip.entry.t1 >= 0 ? 'var(--red)' : 'var(--green)' }}>
                {tip.entry.t1 >= 0 ? '+' : ''}{tip.entry.t1.toFixed(2)}%
              </span>
            </div>
            <div className="matrix-tooltip-row">
              <span>T+2 日累计</span>
              <span style={{ color: tip.entry.t2 >= 0 ? 'var(--red)' : 'var(--green)' }}>
                {tip.entry.t2 >= 0 ? '+' : ''}{tip.entry.t2.toFixed(2)}%
              </span>
            </div>
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
          <div className="matrix-legend-item"><span className="legend-dot" style={{ background: 'var(--red)' }}></span>买入</div>
          <div className="matrix-legend-item"><span className="legend-dot" style={{ background: 'var(--green)' }}></span>卖出</div>
          <div className="matrix-legend-item"><span className="legend-dot" style={{ background: 'var(--orange)' }}></span>持有</div>
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
                      const letter = e.signal ? e.signal[0] : '·';
                      return (
                        <td key={i} className="matrix-td-cell">
                          <div
                            className={`matrix-cell ${e.signal ? signalColor(e.signal) : 'empty'}`}
                            onMouseEnter={(ev) => handleHover(s, tradingDays[i], e, ev.currentTarget)}
                            onMouseLeave={() => setTip(null)}
                          >
                            {letter}
                          </div>
                          <PerfBar t1={e.t1} signal={e.signal} />
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
          <span>底部三色绩效条：红色=信号命中（上涨） 绿色=未命中（下跌） 灰色=无数据</span>
        </div>

        {currentTip}
      </section>
    );
  }

  window.__SHAPE__.dashboardPerformanceMatrix = PerformanceMatrix;
})();
