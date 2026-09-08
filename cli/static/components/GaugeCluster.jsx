(function () {
  const { useApp } = window.__SHAPE__.context;
  const { fmtNum } = window.__SHAPE__.utils;

  // Half-ring gauge
  function Gauge({ value, max, label, unit, band, tone, description }) {
    const pct = Math.min(1, Math.max(0, value / max));
    const angle = Math.PI * pct;
    const r = 78;
    const cx = 100;
    const cy = 100;
    const start = { x: cx - r, y: cy };
    const end = {
      x: cx - r * Math.cos(angle),
      y: cy - r * Math.sin(angle),
    };
    const largeArc = angle > Math.PI ? 1 : 0;
    const bgEnd = { x: cx + r, y: cy };

    const bgPath = `M${start.x} ${start.y} A${r} ${r} 0 0 1 ${bgEnd.x} ${bgEnd.y}`;
    const fgPath = `M${start.x} ${start.y} A${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`;

    // ticks
    const ticks = Array.from({ length: 11 }, (_, i) => {
      const a = Math.PI * (1 - i / 10);
      return {
        x1: cx + (r - 4) * Math.cos(a),
        y1: cy - (r - 4) * Math.sin(a),
        x2: cx + (r + 3) * Math.cos(a),
        y2: cy - (r + 3) * Math.sin(a),
        major: i % 2 === 0,
      };
    });

    return (
      <div className="flex flex-col items-center px-4 py-3 border border-brand-border bg-base-100/60 relative overflow-hidden">
        <div className="absolute top-2 left-3 tab-serif text-primary/80">{label}</div>
        <div className="absolute top-2 right-3 text-[9px] font-mono-num text-brand-muted tracking-wider">
          / {max}{unit}
        </div>

        <svg viewBox="0 0 200 110" className="w-full max-w-[240px] mt-4">
          <defs>
            <linearGradient id={`gauge-${label}`} x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor={tone.from} />
              <stop offset="100%" stopColor={tone.to} />
            </linearGradient>
          </defs>

          {/* ticks */}
          {ticks.map((t, i) => (
            <line
              key={i}
              x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2}
              stroke={t.major ? '#5a6a60' : '#2a3630'}
              strokeWidth={t.major ? 1.2 : 0.6}
            />
          ))}

          {/* bg arc */}
          <path d={bgPath} fill="none" stroke="#1c2823" strokeWidth="10" strokeLinecap="round" />
          {/* fg arc */}
          <path d={fgPath} fill="none" stroke={`url(#gauge-${label})`} strokeWidth="10" strokeLinecap="round" />

          {/* needle */}
          <line
            x1={cx} y1={cy}
            x2={cx - (r - 12) * Math.cos(angle)}
            y2={cy - (r - 12) * Math.sin(angle)}
            stroke="#ecdcb8" strokeWidth="1.8" strokeLinecap="round"
          />
          <circle cx={cx} cy={cy} r="4" fill="#d4a373" stroke="#0e1611" strokeWidth="1" />

          {/* value */}
          <text x={cx} y={cy - 22} textAnchor="middle" fontSize="26" fontFamily="IBM Plex Mono" fontWeight="600" fill="#ecdcb8">
            {typeof value === 'number' ? value.toFixed(value >= 10 && !unit ? 1 : 1) : value}
          </text>
        </svg>

        <div className="mt-1 flex flex-col items-center">
          <div className="inline-flex items-center gap-1.5 px-2 py-0.5 border" style={{ borderColor: tone.to, color: tone.to }}>
            <span className="w-1.5 h-1.5 rounded-full" style={{ background: tone.to }}></span>
            <span className="tab-serif" style={{ letterSpacing: '0.08em' }}>{band}</span>
          </div>
          <p className="text-[10px] text-brand-muted mt-1.5 text-center leading-snug max-w-[200px]">
            {description}
          </p>
        </div>
      </div>
    );
  }

  function GaugeCluster({ variant }) {
    const { activeStock } = useApp();

    // Sentiment view
    if (variant === 'sentiment') {
      const s = activeStock.sentiment;
      const bull = activeStock.bullPct;
      const heat = activeStock.socialHeat;

      const sBand = s >= 7 ? '积极' : s >= 4 ? '中性' : '悲观';
      const bBand = bull >= 60 ? '多头占优' : bull >= 40 ? '多空平衡' : '空头占优';
      const hBand = heat >= 70 ? '高度关注 ↗' : heat >= 40 ? '正常关注' : '关注较少 ↘';

      const gauges = [
        {
          value: s, max: 10, label: '新闻情感得分', unit: '',
          band: sBand,
          tone: s >= 7 ? { from: '#dc2626', to: '#f97316' } : s >= 4 ? { from: '#eab308', to: '#facc15' } : { from: '#0891b2', to: '#22c55e' },
          description: '基于近 48h 财经新闻与研报的加权情感值。',
        },
        {
          value: bull, max: 100, label: '多头占比', unit: '%',
          band: bBand,
          tone: bull >= 60 ? { from: '#dc2626', to: '#f59e0b' } : { from: '#8b5cf6', to: '#3b82f6' },
          description: '主力资金与机构持仓变动结合的多空比。',
        },
        {
          value: heat, max: 100, label: '社交媒体热度', unit: '',
          band: hBand,
          tone: heat >= 70 ? { from: '#d946ef', to: '#f472b6' } : { from: '#6366f1', to: '#3b82f6' },
          description: '雪球、微博、Reddit 等平台聚合的相对热度。',
        },
      ];

      return (
        <div className="grid grid-cols-3 gap-3">
          {gauges.map(g => <Gauge key={g.label} {...g} />)}
        </div>
      );
    }

    // Analyst view: buy / hold / sell distribution + target price band
    if (variant === 'analyst') {
      const report = window.__SHAPE__.mocks.getReport(activeStock.code);
      const { buy, hold, sell, target, consensus } = report.analysts;
      const total = buy + hold + sell;
      const buyPct = (buy / total) * 100;
      const holdPct = (hold / total) * 100;
      const sellPct = (sell / total) * 100;

      const upsidePct = target ? ((target - activeStock.prev) / activeStock.prev) * 100 : 0;

      return (
        <div className="grid grid-cols-3 gap-3">
          <Gauge
            value={buy}
            max={total}
            label="买入 / 增持家数"
            unit=""
            band={buyPct >= 60 ? '强烈推荐' : buyPct >= 40 ? '偏乐观' : '分歧'}
            tone={{ from: '#dc2626', to: '#f97316' }}
            description={`${total} 位分析师中 ${buy} 人推荐买入或增持。`}
          />
          <div className="flex flex-col items-center px-4 py-3 border border-brand-border bg-base-100/60 relative overflow-hidden">
            <div className="absolute top-2 left-3 tab-serif text-primary/80">观点分布</div>
            <div className="absolute top-2 right-3 text-[9px] font-mono-num text-brand-muted">{total} 位</div>

            <div className="mt-6 w-full max-w-[240px]">
              <div className="h-8 flex overflow-hidden border border-brand-border">
                <div className="signal-buy flex items-center justify-center text-[11px] font-mono-num" style={{ width: `${buyPct}%` }}>{buy}</div>
                <div className="signal-hold flex items-center justify-center text-[11px] font-mono-num" style={{ width: `${holdPct}%` }}>{hold}</div>
                <div className="signal-sell flex items-center justify-center text-[11px] font-mono-num" style={{ width: `${sellPct}%` }}>{sell}</div>
              </div>
              <div className="mt-2 grid grid-cols-3 text-[9px] text-brand-muted uppercase tracking-wider">
                <span>Buy</span>
                <span className="text-center">Hold</span>
                <span className="text-right">Sell</span>
              </div>
              <div className="mt-4 border-t border-brand-border pt-3 text-center">
                <div className="tab-serif text-primary">共识评级</div>
                <div className="font-display text-2xl text-base-content mt-1">{consensus}</div>
              </div>
            </div>
          </div>
          <div className="flex flex-col px-4 py-3 border border-brand-border bg-base-100/60 relative overflow-hidden">
            <div className="tab-serif text-primary mb-3">目标价 · 上行空间</div>
            <div className="flex items-baseline gap-3">
              <span className="font-mono-num text-3xl text-primary">{fmtNum(target)}</span>
              <span className="text-[11px] text-brand-muted font-mono-num">目标价</span>
            </div>
            <div className="mt-1 font-mono-num text-lg" style={{ color: upsidePct >= 0 ? '#ef4444' : '#22c55e' }}>
              {upsidePct >= 0 ? '+' : ''}{upsidePct.toFixed(1)}% 空间
            </div>

            <div className="mt-4 relative h-3 bg-base-300">
              <div className="absolute top-0 bottom-0 bg-emerald-700" style={{ left: 0, width: '30%' }}></div>
              <div className="absolute top-0 bottom-0 bg-yellow-600" style={{ left: '30%', width: '40%' }}></div>
              <div className="absolute top-0 bottom-0 bg-red-600" style={{ left: '70%', right: 0 }}></div>
              <div className="absolute -top-1 w-0.5 h-5 bg-primary" style={{ left: `${Math.min(95, Math.max(5, 50 + upsidePct / 2))}%` }}></div>
            </div>
            <div className="mt-1 flex justify-between text-[9px] text-brand-muted font-mono-num">
              <span>低估</span><span>合理</span><span>高估</span>
            </div>

            <div className="mt-4 text-[10px] text-brand-muted leading-relaxed">
              目标价为 {total} 家投行 12 个月目标价中位数,较昨收 <span className="font-mono-num text-base-content">{fmtNum(activeStock.prev)}</span> 具备
              <span className="font-mono-num" style={{ color: upsidePct >= 0 ? '#ef4444' : '#22c55e' }}> {Math.abs(upsidePct).toFixed(1)}% </span>
              的{upsidePct >= 0 ? '上行' : '下行'}空间。
            </div>
          </div>
        </div>
      );
    }

    return null;
  }

  window.__SHAPE__.GaugeCluster = GaugeCluster;
})();
