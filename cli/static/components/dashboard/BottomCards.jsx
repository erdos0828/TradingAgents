(function () {
  const { useDashboard } = window.__SHAPE__.dashboardContext;
  const { signalColor, signalLabel } = window.__SHAPE__.dashboardUtils;

  function recColor(rec) {
    if (/BUY/i.test(rec)) return 'var(--red)';
    if (/SELL/i.test(rec)) return 'var(--green)';
    return 'var(--text)';
  }

  function BottomCards() {
    const { sentiment, analyst, financial } = useDashboard();

    return (
      <div className="bottom-row">
        <div className="analysis-card">
          <div className="card-title">
            情绪分析
            {sentiment.reportDate && <span className="subtitle">{sentiment.reportDate} 报告</span>}
          </div>
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
          {sentiment.roles && sentiment.roles.length > 0 && (
            <div className="role-badges">
              {sentiment.roles.map((r) => (
                <span key={r.role} className={`role-badge ${signalColor(r.rating)}`}>
                  <span className="role-name">{r.roleName}</span>
                  <span>{signalLabel(r.rating)}</span>
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="analysis-card">
          <div className="card-title">
            分析师观点
            {analyst.taDate && <span className="subtitle">TradingView {analyst.taDate}</span>}
          </div>
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
          {analyst.recommendation && (
            <div className="analyst-meta">
              <span>
                综合评级 <strong style={{ color: recColor(analyst.recommendation) }}>{analyst.recommendation}</strong>
              </span>
              <span className="analyst-votes">
                买入 {analyst.buyVotes} · 卖出 {analyst.sellVotes} · 中性 {analyst.neutralVotes}
              </span>
            </div>
          )}
        </div>

        <div className="analysis-card">
          <div className="card-title">
            财务摘要
            {financial.reportDate && <span className="subtitle">{financial.reportDate} 报告</span>}
          </div>
          <div className="financial-grid">
            <div className="financial-item">
              <div className="label">{financial.peForward ? 'PE(前向)' : 'PE(TTM)'}</div>
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
