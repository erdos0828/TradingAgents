(function () {
  const { useApp } = window.__SHAPE__.context;

  const TABS = [
    { id: 'core',      label: '核心报告',   sub: 'Core',      kind: 'paper' },
    { id: 'sentiment', label: '情绪分析',   sub: 'Sentiment', kind: 'gauge' },
    { id: 'analyst',   label: '分析师观点', sub: 'Analyst',   kind: 'gauge' },
    { id: 'financial', label: '财务摘要',   sub: 'Financial', kind: 'paper' },
    { id: 'risk',      label: '风险管理',   sub: 'Risk',      kind: 'paper' },
    { id: 'technical', label: '技术指标',   sub: 'Technical', kind: 'paper' },
  ];

  function GaugeShell({ children, kicker, title, desc }) {
    return (
      <div className="bg-base-100/50 border border-brand-border p-5">
        <header className="mb-4 flex items-baseline justify-between">
          <div>
            <div className="tab-serif text-primary">{kicker}</div>
            <h3 className="font-display text-2xl text-base-content mt-0.5">{title}</h3>
          </div>
          <div className="text-[11px] text-brand-muted max-w-xs text-right leading-relaxed">
            {desc}
          </div>
        </header>
        {children}
      </div>
    );
  }

  function AnalysisTabs() {
    const { activeTab, setActiveTab, activeStock } = useApp();
    const { GaugeCluster, ReportPaper } = window.__SHAPE__;

    let body;
    if (activeTab === 'sentiment') {
      body = (
        <GaugeShell
          kicker="Sentiment Dashboard · 情绪三叉戟"
          title="市场情绪静态透视"
          desc="收盘后一次结账,三口径独立采集,不追高频波动。"
        >
          <GaugeCluster variant="sentiment" />
          <div className="mt-4 grid grid-cols-3 gap-3 text-[11px] text-brand-muted">
            <div className="p-3 border border-brand-border/60 bg-base-200/40">
              <div className="tab-serif text-primary mb-1">📰 新闻源头</div>
              财联社 · 证券时报 · 同花顺研报库 · Bloomberg 中文
            </div>
            <div className="p-3 border border-brand-border/60 bg-base-200/40">
              <div className="tab-serif text-primary mb-1">📊 资金结构</div>
              北向持仓 · 主力资金流向 · 机构调研次数
            </div>
            <div className="p-3 border border-brand-border/60 bg-base-200/40">
              <div className="tab-serif text-primary mb-1">🌐 社群平台</div>
              雪球 · 东方财富股吧 · 微博财经 · Reddit r/investing
            </div>
          </div>
        </GaugeShell>
      );
    } else if (activeTab === 'analyst') {
      body = (
        <GaugeShell
          kicker="Analyst Consensus · 分析师观点"
          title="卖方共识与目标价"
          desc="覆盖近 30 日 12 家主流投行的研报,静态汇总。"
        >
          <GaugeCluster variant="analyst" />
        </GaugeShell>
      );
    } else if (activeTab === 'financial') {
      body = <ReportPaper.FinancialReport />;
    } else if (activeTab === 'risk') {
      body = <ReportPaper.RiskReport />;
    } else if (activeTab === 'technical') {
      body = <ReportPaper.TechnicalReport />;
    } else {
      body = <ReportPaper.CoreReport />;
    }

    return (
      <section className="panel">
        {/* tab strip */}
        <nav className="flex items-stretch border-b border-brand-border bg-base-300/40 overflow-x-auto scroll-thin">
          <div className="flex items-center gap-2 px-4 py-3 border-r border-brand-border">
            <span className="tab-serif text-primary">▶</span>
            <span className="tab-serif text-brand-muted">多维静态分析工作台</span>
          </div>
          {TABS.map((t, i) => {
            const isActive = t.id === activeTab;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setActiveTab(t.id)}
                className={`relative px-5 py-3 border-r border-brand-border flex flex-col items-start gap-0.5 transition min-w-[130px] ${isActive ? 'bg-primary/10 text-primary' : 'text-brand-muted hover:text-base-content hover:bg-base-200/50'}`}
              >
                <span className="tab-serif" style={{ letterSpacing: '0.12em' }}>{t.sub}</span>
                <span className="font-display text-lg leading-tight" style={{ color: isActive ? 'var(--color-primary)' : 'var(--color-base-content)' }}>
                  {t.label}
                </span>
                {isActive && (
                  <span
                    className="absolute bottom-0 left-0 right-0 h-[3px] bg-primary tab-mark-in"
                    style={{ boxShadow: '0 0 12px rgba(212,163,115,0.6)' }}
                  ></span>
                )}
                {isActive && (
                  <span className="absolute top-2 right-2 text-[9px] font-mono-num text-primary">0{i + 1}</span>
                )}
              </button>
            );
          })}
          <div className="flex-1 flex items-center justify-end px-4 py-3 border-r border-brand-border">
            <span className="text-[10px] text-brand-muted font-mono-num">
              当前 · {activeStock.name} · {activeStock.code}
            </span>
          </div>
        </nav>

        {/* body */}
        <div className="p-4">
          <div key={activeTab + activeStock.code} className="candle-in">
            {body}
          </div>
        </div>
      </section>
    );
  }

  window.__SHAPE__.AnalysisTabs = AnalysisTabs;
})();
