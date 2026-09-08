(function () {
  const { useDashboard } = window.__SHAPE__.dashboardContext;

  function PortfolioPanel() {
    const { portfolio, holdings, activeHoldingIdx, setActiveHoldingIdx } = useDashboard();

    return (
      <section className="card">
        <div className="card-title">
          持仓全局看板
          <span className="subtitle">实时估值</span>
        </div>
        <div className="portfolio-summary">
          <div className="portfolio-total">{portfolio.total}</div>
          <div className="portfolio-change">
            <span className="amount" style={{ color: portfolio.up ? 'var(--red)' : 'var(--green)' }}>
              {portfolio.changeAmount}
            </span>
            <span
              className="percent"
              style={{
                background: portfolio.up ? 'var(--red-light)' : 'var(--green-light)',
                color: portfolio.up ? 'var(--red)' : 'var(--green)',
              }}
            >
              {portfolio.changePercent}
            </span>
          </div>
        </div>
        <div className="holdings-list">
          {holdings.map((h, idx) => (
            <div
              key={h.code}
              className={`holding-item ${idx === activeHoldingIdx ? 'active' : ''}`}
              onClick={() => setActiveHoldingIdx(idx)}
            >
              <div>
                <div className="holding-name">{h.name}</div>
                <div className="holding-code">{h.code} · 权重 {h.weight}</div>
              </div>
              <div className="holding-price">{h.price}</div>
              <div className={`holding-change ${h.up ? 'up' : 'down'}`}>{h.change}</div>
            </div>
          ))}
        </div>
      </section>
    );
  }

  window.__SHAPE__.dashboardPortfolioPanel = PortfolioPanel;
})();
