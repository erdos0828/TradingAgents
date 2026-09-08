(function () {
  const { useApp } = window.__SHAPE__.context;
  const { fmtNum } = window.__SHAPE__.utils;

  function VerdictStamp({ verdict, label, dateStr }) {
    const color = verdict === 'BUY' ? '#dc2626' : verdict === 'SELL' ? '#16a34a' : '#ca8a04';
    return (
      <div
        className="inline-flex flex-col items-center px-4 py-2 border-2"
        style={{ borderColor: color, color, transform: 'rotate(-3deg)' }}
      >
        <span className="tab-serif" style={{ letterSpacing: '0.2em' }}>Verdict</span>
        <span className="font-display text-2xl leading-none mt-0.5" style={{ letterSpacing: '0.05em' }}>{label}</span>
        <span className="tab-serif text-[9px] mt-0.5" style={{ letterSpacing: '0.15em' }}>{verdict} · {dateStr}</span>
      </div>
    );
  }

  function CoreReport() {
    const { activeStock, activeDate } = useApp();
    const r = window.__SHAPE__.mocks.getReport(activeStock.code);
    const dateStamp = activeDate.date.replace(/-/g, '·');
    const sigStamp = activeDate.date.replace(/-/g, '');

    return (
      <div className="paper grain relative p-8 pr-24 min-h-[400px]">
        <div className="absolute top-6 right-8">
          <VerdictStamp verdict={r.verdict} label={r.verdictLabel} dateStr={dateStamp} />
        </div>

        <header className="mb-6 pb-4 border-b-2 border-double" style={{ borderColor: '#8b6c3f' }}>
          <div className="tab-serif" style={{ color: '#8b6c3f', letterSpacing: '0.25em' }}>
            核心报告 · Core Thesis
          </div>
          <h2 className="font-display text-4xl mt-2 leading-tight" style={{ color: '#1a1912' }}>
            {activeStock.name} <span className="italic text-2xl" style={{ color: '#8b6c3f' }}>· {activeStock.code}</span>
          </h2>
          <p className="font-serif-body text-base mt-3 leading-relaxed" style={{ color: '#3a3628' }}>
            {r.thesis}
          </p>
        </header>

        <section className="mb-5">
          <h3 className="font-display text-lg mb-3" style={{ color: '#1a1912' }}>
            多角色观点静态碰撞
          </h3>
          <div className="space-y-3 text-[13px]">
            {[
              { role: 'Conservative Analyst', tag: '风控', color: '#16a34a', text: r.conservative },
              { role: 'Aggressive Analyst', tag: '进攻', color: '#dc2626', text: r.aggressive },
              { role: 'Neutral Analyst', tag: '中性', color: '#8b6c3f', text: r.neutral },
            ].map(v => (
              <div key={v.role} className="flex gap-3">
                <div className="flex-shrink-0 pt-0.5">
                  <div className="tab-serif px-1.5 py-0.5 text-[9px]" style={{ background: v.color, color: '#fff', letterSpacing: '0.15em' }}>
                    {v.tag}
                  </div>
                </div>
                <div className="flex-1">
                  <div className="font-serif-body italic text-[11px]" style={{ color: v.color }}>&gt; {v.role}</div>
                  <div className="font-serif-body mt-0.5 leading-relaxed" style={{ color: '#1a1912' }}>
                    {v.text}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <div className="grid grid-cols-2 gap-4 mt-6">
          <section>
            <h4 className="tab-serif mb-2" style={{ color: '#dc2626', letterSpacing: '0.2em' }}>
              ▲ 关键催化剂
            </h4>
            <ul className="space-y-1.5 text-[12px] font-serif-body" style={{ color: '#1a1912' }}>
              {r.catalysts.map((c, i) => (
                <li key={i} className="flex gap-2">
                  <span style={{ color: '#dc2626' }}>{String(i + 1).padStart(2, '0')}</span>
                  <span>{c}</span>
                </li>
              ))}
            </ul>
          </section>
          <section>
            <h4 className="tab-serif mb-2" style={{ color: '#16a34a', letterSpacing: '0.2em' }}>
              ▼ 关键风险
            </h4>
            <ul className="space-y-1.5 text-[12px] font-serif-body" style={{ color: '#1a1912' }}>
              {r.risks.map((c, i) => (
                <li key={i} className="flex gap-2">
                  <span style={{ color: '#16a34a' }}>{String(i + 1).padStart(2, '0')}</span>
                  <span>{c}</span>
                </li>
              ))}
            </ul>
          </section>
        </div>

        <footer className="mt-6 pt-3 border-t text-[10px] flex items-center justify-between" style={{ borderColor: '#c8b590', color: '#8b6c3f' }}>
          <span className="font-mono-num">SIG-{activeStock.code}-{sigStamp}</span>
          <span className="tab-serif" style={{ letterSpacing: '0.2em' }}>本刊由智投研究所静态排印 · 收盘后一次结账</span>
        </footer>
      </div>
    );
  }

  function FinancialReport() {
    const { activeStock } = useApp();
    const r = window.__SHAPE__.mocks.getReport(activeStock.code);
    const f = r.financial;

    const rows = [
      { label: '营业收入', value: f.revenue, delta: f.revenueYoy, key: 'REV' },
      { label: '归母净利润', value: f.netProfit, delta: f.netProfitYoy, key: 'NP' },
      { label: '毛利率', value: f.gross, key: 'GM' },
      { label: 'ROE', value: f.roe, key: 'ROE' },
    ];

    const ratios = [
      { label: 'P/E', value: f.pe },
      { label: 'P/B', value: f.pb },
      { label: 'EPS', value: f.eps },
      { label: 'DPS', value: f.dps },
    ];

    return (
      <div className="paper grain relative p-8 min-h-[400px]">
        <header className="mb-4 pb-3 flex items-baseline justify-between" style={{ borderBottom: '3px double #8b6c3f' }}>
          <div>
            <div className="tab-serif" style={{ color: '#8b6c3f', letterSpacing: '0.25em' }}>Financial Snapshot · 财务摘要</div>
            <h2 className="font-display text-3xl mt-1" style={{ color: '#1a1912' }}>{activeStock.name} 财报速览</h2>
          </div>
          <div className="text-[10px] font-mono-num" style={{ color: '#8b6c3f' }}>报告期 · 2026 H1</div>
        </header>

        <section className="grid grid-cols-4 gap-3 mb-6">
          {rows.map(r => (
            <div key={r.key} className="border p-3" style={{ borderColor: '#c8b590', background: 'rgba(255,255,255,0.35)' }}>
              <div className="tab-serif text-[9px] mb-1" style={{ color: '#8b6c3f', letterSpacing: '0.2em' }}>{r.label}</div>
              <div className="font-mono-num text-2xl" style={{ color: '#1a1912' }}>{r.value}</div>
              {r.delta && (
                <div className="font-mono-num text-[11px] mt-1" style={{ color: r.delta.startsWith('+') ? '#dc2626' : '#16a34a' }}>
                  YoY {r.delta}
                </div>
              )}
            </div>
          ))}
        </section>

        <section className="mb-6">
          <h3 className="tab-serif mb-3" style={{ color: '#8b6c3f', letterSpacing: '0.2em' }}>估值倍数</h3>
          <div className="grid grid-cols-4 border-t border-b" style={{ borderColor: '#8b6c3f' }}>
            {ratios.map((r, i) => (
              <div key={r.label} className={`px-4 py-3 ${i < 3 ? 'border-r' : ''}`} style={{ borderColor: '#c8b590' }}>
                <div className="tab-serif text-[9px]" style={{ color: '#8b6c3f' }}>{r.label}</div>
                <div className="font-mono-num text-xl mt-0.5" style={{ color: '#1a1912' }}>{r.value}</div>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h3 className="tab-serif mb-3" style={{ color: '#8b6c3f', letterSpacing: '0.2em' }}>近 4 季度趋势</h3>
          <div className="flex items-end gap-2 h-24">
            {[68, 74, 62, 82].map((h, i) => (
              <div key={i} className="flex-1 flex flex-col items-center">
                <div className="w-full relative" style={{ background: '#8b6c3f', height: `${h}%` }}>
                  <div className="absolute inset-0" style={{ backgroundImage: 'repeating-linear-gradient(45deg, transparent 0 2px, rgba(0,0,0,0.15) 2px 3px)' }}></div>
                </div>
                <div className="font-mono-num text-[9px] mt-1" style={{ color: '#8b6c3f' }}>Q{i + 1}</div>
              </div>
            ))}
          </div>
        </section>
      </div>
    );
  }

  function RiskReport() {
    const { activeStock } = useApp();
    const r = window.__SHAPE__.mocks.getReport(activeStock.code);

    const dims = [
      { name: '市场波动率', level: 3, note: 'β 系数 1.14, 位于行业中位。' },
      { name: '流动性风险', level: 2, note: '日均换手率健康,可承受 5000 万级别调仓。' },
      { name: '事件驱动风险', level: 4, note: '临近财报窗口,警惕业绩指引变化。' },
      { name: '监管政策风险', level: 3, note: '所处行业政策方向偏中性,无明确利空。' },
      { name: '外汇/宏观风险', level: 2, note: '汇率暴露有限,美联储路径已被计入。' },
    ];

    return (
      <div className="paper grain relative p-8 min-h-[400px]">
        <header className="mb-4 pb-3" style={{ borderBottom: '3px double #8b6c3f' }}>
          <div className="tab-serif" style={{ color: '#8b6c3f', letterSpacing: '0.25em' }}>Risk Management · 风险管理</div>
          <h2 className="font-display text-3xl mt-1" style={{ color: '#1a1912' }}>风险画像与建议仓位</h2>
          <p className="font-serif-body text-[12px] mt-2" style={{ color: '#3a3628' }}>
            综合五维评分后,系统建议核心仓位不超过 <span className="font-mono-num" style={{ color: '#dc2626' }}>组合的 8%</span>,
            单笔加仓幅度不超过 <span className="font-mono-num" style={{ color: '#dc2626' }}>剩余现金的 20%</span>。
          </p>
        </header>

        <section className="space-y-3">
          {dims.map(d => (
            <div key={d.name} className="grid grid-cols-[1fr_auto_2fr] gap-4 items-center pb-2" style={{ borderBottom: '1px dashed #c8b590' }}>
              <div className="font-serif-body text-[13px]" style={{ color: '#1a1912' }}>{d.name}</div>
              <div className="flex gap-0.5">
                {Array.from({ length: 5 }).map((_, i) => (
                  <div key={i} className="w-4 h-4 border" style={{
                    borderColor: '#8b6c3f',
                    background: i < d.level ? (d.level >= 4 ? '#dc2626' : d.level >= 3 ? '#ca8a04' : '#16a34a') : 'transparent',
                  }}></div>
                ))}
              </div>
              <div className="font-serif-body text-[11px]" style={{ color: '#3a3628' }}>{d.note}</div>
            </div>
          ))}
        </section>

        <section className="mt-6 p-4 border-2" style={{ borderColor: '#dc2626', background: 'rgba(220,38,38,0.06)' }}>
          <div className="tab-serif mb-2" style={{ color: '#dc2626', letterSpacing: '0.2em' }}>⚠ 硬止损线</div>
          <div className="font-serif-body text-[12px]" style={{ color: '#1a1912' }}>
            当收盘价跌破 <span className="font-mono-num" style={{ color: '#dc2626' }}>{fmtNum(activeStock.prev * 0.92)}</span> 时触发系统止损,
            对应目前昨收 <span className="font-mono-num">{fmtNum(activeStock.prev)}</span> 的 <span className="font-mono-num">-8.0%</span>。
          </div>
        </section>
      </div>
    );
  }

  function TechnicalReport() {
    const { activeStock } = useApp();
    const r = window.__SHAPE__.mocks.getReport(activeStock.code);
    const t = r.technical;

    const rows = [
      { label: '趋势结构', value: t.trend, tone: t.trend.includes('上') || t.trend.includes('底') ? '#dc2626' : '#8b6c3f' },
      { label: 'RSI (14)', value: t.rsi, tone: t.rsi > 70 ? '#dc2626' : t.rsi < 30 ? '#16a34a' : '#8b6c3f' },
      { label: 'MACD', value: t.macd, tone: '#8b6c3f' },
      { label: 'KDJ', value: t.kdj, tone: '#8b6c3f' },
      { label: '关键支撑', value: fmtNum(t.support), tone: '#16a34a' },
      { label: '关键阻力', value: fmtNum(t.resistance), tone: '#dc2626' },
    ];

    return (
      <div className="paper grain relative p-8 min-h-[400px]">
        <header className="mb-4 pb-3" style={{ borderBottom: '3px double #8b6c3f' }}>
          <div className="tab-serif" style={{ color: '#8b6c3f', letterSpacing: '0.25em' }}>Technical Read · 技术指标</div>
          <h2 className="font-display text-3xl mt-1" style={{ color: '#1a1912' }}>形态与量能拓印</h2>
        </header>

        <section className="grid grid-cols-2 gap-x-8 gap-y-3">
          {rows.map(row => (
            <div key={row.label} className="flex items-baseline justify-between pb-2" style={{ borderBottom: '1px dashed #c8b590' }}>
              <span className="font-serif-body text-[13px]" style={{ color: '#1a1912' }}>{row.label}</span>
              <span className="font-mono-num text-lg" style={{ color: row.tone }}>{row.value}</span>
            </div>
          ))}
        </section>

        <section className="mt-6">
          <h3 className="tab-serif mb-3" style={{ color: '#8b6c3f', letterSpacing: '0.2em' }}>价格通道</h3>
          <div className="relative h-32 border" style={{ borderColor: '#c8b590', background: 'rgba(255,255,255,0.3)' }}>
            <div className="absolute inset-0" style={{
              backgroundImage: 'repeating-linear-gradient(0deg, transparent 0 15px, rgba(139,108,63,0.15) 15px 16px)',
            }}></div>
            {/* draw pseudo lines */}
            <svg viewBox="0 0 400 120" className="absolute inset-0 w-full h-full">
              <path d="M0,80 C60,60 120,90 180,70 C240,50 300,80 400,60" fill="none" stroke="#dc2626" strokeWidth="1.5" />
              <path d="M0,100 C60,90 120,100 180,95 C240,80 300,90 400,85" fill="none" stroke="#16a34a" strokeWidth="1.5" strokeDasharray="3,2" />
              <line x1="0" y1="30" x2="400" y2="30" stroke="#dc2626" strokeWidth="0.7" strokeDasharray="1,3" />
              <line x1="0" y1="110" x2="400" y2="110" stroke="#16a34a" strokeWidth="0.7" strokeDasharray="1,3" />
              <text x="6" y="26" fontSize="9" fill="#dc2626" fontFamily="IBM Plex Mono">阻力 {fmtNum(t.resistance)}</text>
              <text x="6" y="118" fontSize="9" fill="#16a34a" fontFamily="IBM Plex Mono">支撑 {fmtNum(t.support)}</text>
            </svg>
          </div>
          <p className="font-serif-body text-[11px] mt-3 leading-relaxed" style={{ color: '#3a3628' }}>
            价格在关键支撑上方运行,若能有效突破阻力位并伴随放量,趋势结构有望进一步强化。
            量价背离需关注 MACD 二次零轴粘连信号。
          </p>
        </section>
      </div>
    );
  }

  window.__SHAPE__.ReportPaper = { CoreReport, FinancialReport, RiskReport, TechnicalReport };
})();
