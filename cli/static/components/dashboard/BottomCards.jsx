(function () {
  const { useDashboard } = window.__SHAPE__.dashboardContext;

  function BottomCards() {
    const { sentiment, analyst, financial } = useDashboard();

    return (
      <div className="bottom-row">
        <div className="analysis-card">
          <div className="card-title">情绪分析</div>
          <div className="gauge-wrapper">
            <div className="semi-gauge">
              <div
                className="semi-gauge-needle"
                style={{ transform: `translateX(-50%) rotate(${sentiment.angle}deg)` }}
              ></div>
            </div>
            <div className="gauge-info">
              <div className="gauge-score">{sentiment.score}</div>
              <div className="gauge-label">{sentiment.label}</div>
            </div>
          </div>
          <div className="sentiment-labels">
            <span>极度恐惧</span>
            <span>中立</span>
            <span>极度贪婪</span>
          </div>
        </div>

        <div className="analysis-card">
          <div className="card-title">分析师观点</div>
          <div className="bar-chart">
            <div className="bar-track">
              <div className="bar-segment bull" style={{ width: analyst.bull + '%' }}></div>
              <div className="bar-segment bear" style={{ width: analyst.bear + '%' }}></div>
            </div>
          </div>
          <div className="bar-labels">
            <span style={{ color: 'var(--red)' }}>
              多头占优 <strong>{analyst.bull}%</strong>
            </span>
            <span style={{ color: 'var(--green)' }}>
              空头 <strong>{analyst.bear}%</strong>
            </span>
          </div>
        </div>

        <div className="analysis-card">
          <div className="card-title">财务摘要</div>
          <div className="financial-grid">
            <div className="financial-item">
              <div className="label">PE(TTM)</div>
              <div className="value">{financial.pe}</div>
            </div>
            <div className="financial-item">
              <div className="label">PB</div>
              <div className="value">{financial.pb}</div>
            </div>
            <div className="financial-item">
              <div className="label">ROE</div>
              <div className="value">{financial.roe}</div>
            </div>
            <div className="financial-item">
              <div className="label">毛利率</div>
              <div className="value">{financial.margin}</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  window.__SHAPE__.dashboardBottomCards = BottomCards;
})();
