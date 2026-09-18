(function () {
  const { useApp } = window.__SHAPE__.context;
  const { buildKLine } = window.__SHAPE__.mocks;
  const { fmtNum, fmtPct } = window.__SHAPE__.utils;

  function KLineChart() {
    const { activeStock, market } = useApp();
    const bars = React.useMemo(() => buildKLine(activeStock), [activeStock.code]);

    const width = 720;
    const height = 260;
    const paddingL = 44;
    const paddingR = 60;
    const paddingT = 24;
    const paddingB = 26;

    const highs = bars.map(b => b.high);
    const lows = bars.map(b => b.low);
    const maxP = Math.max(...highs);
    const minP = Math.min(...lows);
    const priceRange = maxP - minP;
    const paddedMax = maxP + priceRange * 0.08;
    const paddedMin = minP - priceRange * 0.06;

    const y = (p) => paddingT + (paddedMax - p) / (paddedMax - paddedMin) * (height - paddingT - paddingB);
    const barW = (width - paddingL - paddingR) / bars.length;

    // MA5, MA10, MA20 as running averages
    function movingAvg(n) {
      const out = [];
      for (let i = 0; i < bars.length; i++) {
        const s = Math.max(0, i - n + 1);
        const slice = bars.slice(s, i + 1);
        const avg = slice.reduce((a, b) => a + b.close, 0) / slice.length;
        out.push(avg);
      }
      return out;
    }
    const ma5 = movingAvg(5);
    const ma10 = movingAvg(10);
    const ma20 = movingAvg(20);

    const path = (arr) => arr.map((v, i) => {
      const cx = paddingL + i * barW + barW / 2;
      const cy = y(v);
      return `${i === 0 ? 'M' : 'L'}${cx.toFixed(1)},${cy.toFixed(1)}`;
    }).join(' ');

    // gridlines
    const gridCount = 5;
    const gridLines = Array.from({ length: gridCount + 1 }, (_, i) => {
      const p = paddedMin + (paddedMax - paddedMin) * (i / gridCount);
      return { p, y: y(p) };
    });

    // last close/change indicator
    const last = bars[bars.length - 1];
    const first = bars[0];
    const rangeChange = ((last.close - first.close) / first.close) * 100;

    const currency = market === 'A' ? '¥' : '$';

    return (
      <section className="panel relative overflow-hidden">
        {/* header row */}
        <header className="px-5 pt-4 pb-3 border-b border-brand-border flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <span className="tab-serif text-primary">Ticker · 个股速览与走势舱</span>
              <span className="inline-flex items-center gap-1 text-[10px] text-brand-muted font-mono-num">
                <span className="w-1.5 h-1.5 rounded-full bg-primary pulse-dot"></span>
                收盘结账
              </span>
            </div>
            <div className="flex items-baseline gap-4 flex-wrap">
              <h1 className="font-display text-3xl text-base-content">
                {activeStock.name}
              </h1>
              <span className="font-mono-num text-sm text-brand-muted">{activeStock.code}</span>
              <span className="font-mono-num text-3xl text-primary">
                {currency}{fmtNum(activeStock.prev)}
              </span>
              <span className={`font-mono-num text-sm ${activeStock.changePct >= 0 ? 'text-red-400' : 'text-emerald-400'}`}>
                {activeStock.change >= 0 ? '+' : ''}{fmtNum(activeStock.change)} · {fmtPct(activeStock.changePct)}
              </span>
            </div>
          </div>

        </header>

        {/* stats strip */}
        <div className="grid grid-cols-6 border-b border-brand-border text-[11px]">
          {[
            { label: 'MA5',   value: fmtNum(activeStock.ma5),  color: '#eab308' },
            { label: 'MA10',  value: fmtNum(activeStock.ma10), color: '#3b82f6' },
            { label: 'MA20',  value: fmtNum(activeStock.ma20), color: '#a855f7' },
            { label: '成交量', value: activeStock.volume,       color: '#8a8676' },
            { label: '52W H', value: fmtNum(activeStock.high52),color: '#ef4444' },
            { label: '52W L', value: fmtNum(activeStock.low52), color: '#22c55e' },
          ].map((it, i) => (
            <div key={it.label} className={`px-4 py-2 flex flex-col ${i < 5 ? 'border-r border-brand-border/60' : ''}`}>
              <span className="text-[9px] uppercase tracking-[0.2em]" style={{ color: it.color }}>{it.label}</span>
              <span className="font-mono-num text-[13px] text-base-content mt-0.5">{it.value}</span>
            </div>
          ))}
        </div>

        {/* chart body */}
        <div className="p-4 bg-gradient-to-b from-base-100 to-base-200 relative">
          <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto" preserveAspectRatio="none">
            <defs>
              <pattern id="paper-grain" width="4" height="4" patternUnits="userSpaceOnUse">
                <circle cx="1" cy="1" r="0.5" fill="rgba(236,220,184,0.03)" />
              </pattern>
              <filter id="rough" x="-5%" y="-5%" width="110%" height="110%">
                <feTurbulence type="fractalNoise" baseFrequency="1.4" numOctaves="1" seed="3"/>
                <feDisplacementMap in="SourceGraphic" scale="0.7" />
              </filter>
              <linearGradient id="fadeArea" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="rgba(212,163,115,0.15)" />
                <stop offset="100%" stopColor="rgba(212,163,115,0)" />
              </linearGradient>
            </defs>

            <rect x="0" y="0" width={width} height={height} fill="url(#paper-grain)" />

            {/* horizontal gridlines with price labels */}
            {gridLines.map((g, i) => (
              <g key={i}>
                <line
                  x1={paddingL} x2={width - paddingR}
                  y1={g.y} y2={g.y}
                  stroke="#2a3630" strokeWidth="0.5" strokeDasharray="2,3"
                />
                <text
                  x={paddingL - 6} y={g.y + 3}
                  textAnchor="end" fontSize="9"
                  fill="#746d7d" fontFamily="IBM Plex Mono"
                >
                  {g.p.toFixed(g.p > 100 ? 0 : 2)}
                </text>
                <text
                  x={width - paddingR + 6} y={g.y + 3}
                  textAnchor="start" fontSize="9"
                  fill="#746d7d" fontFamily="IBM Plex Mono"
                >
                  {g.p.toFixed(g.p > 100 ? 0 : 2)}
                </text>
              </g>
            ))}

            {/* left / right axis rules */}
            <line x1={paddingL} y1={paddingT} x2={paddingL} y2={height - paddingB} stroke="#3a4a42" strokeWidth="1" />
            <line x1={width - paddingR} y1={paddingT} x2={width - paddingR} y2={height - paddingB} stroke="#3a4a42" strokeWidth="1" />
            <line x1={paddingL} y1={height - paddingB} x2={width - paddingR} y2={height - paddingB} stroke="#3a4a42" strokeWidth="1" />

            {/* candles */}
            {bars.map((b, i) => {
              const cx = paddingL + i * barW + barW / 2;
              const bodyTop = y(Math.max(b.open, b.close));
              const bodyBot = y(Math.min(b.open, b.close));
              const bodyH = Math.max(bodyBot - bodyTop, 1);
              const color = b.up ? '#ef4444' : '#22c55e';
              const opacity = 0.4 + (i / bars.length) * 0.55;
              return (
                <g key={i} className="candle-in" style={{ animationDelay: `${i * 6}ms` }}>
                  <line
                    x1={cx} x2={cx}
                    y1={y(b.high)} y2={y(b.low)}
                    stroke={color} strokeWidth="0.8" opacity={opacity}
                  />
                  <rect
                    x={cx - barW * 0.32}
                    y={bodyTop}
                    width={barW * 0.64}
                    height={bodyH}
                    fill={b.up ? color : 'transparent'}
                    stroke={color}
                    strokeWidth="1"
                    opacity={opacity}
                  />
                </g>
              );
            })}

            {/* MA lines with etched feel */}
            <path d={path(ma20)} fill="none" stroke="#a855f7" strokeWidth="1.2" strokeDasharray="3,2" opacity="0.7" />
            <path d={path(ma10)} fill="none" stroke="#3b82f6" strokeWidth="1.4" opacity="0.85" />
            <path d={path(ma5)}  fill="none" stroke="#eab308" strokeWidth="1.6" opacity="0.95" />

            {/* last price marker */}
            {(() => {
              const cx = paddingL + (bars.length - 1) * barW + barW / 2;
              const cy = y(last.close);
              return (
                <g>
                  <line x1={paddingL} y1={cy} x2={width - paddingR} y2={cy} stroke="#d4a373" strokeWidth="0.6" strokeDasharray="1,2" opacity="0.7" />
                  <rect x={width - paddingR + 2} y={cy - 8} width={paddingR - 4} height={16} fill="#d4a373" />
                  <text x={width - paddingR / 2} y={cy + 3} textAnchor="middle" fontSize="10" fontWeight="600" fill="#0e1611" fontFamily="IBM Plex Mono">
                    {last.close.toFixed(last.close > 100 ? 0 : 2)}
                  </text>
                  <circle cx={cx} cy={cy} r="3" fill="#d4a373" />
                  <circle cx={cx} cy={cy} r="6" fill="none" stroke="#d4a373" strokeWidth="0.8" opacity="0.6" />
                </g>
              );
            })()}

            {/* range summary */}
            <text x={paddingL + 6} y={paddingT + 14} fontSize="10" fill="#8a8676" fontFamily="IBM Plex Sans">
              60 交易日
            </text>
            <text x={paddingL + 6} y={paddingT + 28} fontSize="11" fill={rangeChange >= 0 ? '#ef4444' : '#22c55e'} fontFamily="IBM Plex Mono" fontWeight="600">
              区间 {rangeChange >= 0 ? '+' : ''}{rangeChange.toFixed(2)}%
            </text>
          </svg>

          {/* legend */}
          <div className="absolute bottom-6 right-16 flex items-center gap-4 text-[10px] font-mono-num text-brand-muted">
            <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-yellow-500"></span>MA5</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-blue-500"></span>MA10</span>
            <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-purple-500 opacity-70" style={{ backgroundImage: 'repeating-linear-gradient(90deg, currentColor 0 2px, transparent 2px 4px)' }}></span>MA20</span>
          </div>
        </div>
      </section>
    );
  }

  window.__SHAPE__.KLineChart = KLineChart;
})();
