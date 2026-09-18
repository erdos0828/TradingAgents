(function () {
  const { useDashboard } = window.__SHAPE__.dashboardContext;
  const { signalColor, signalLabel } = window.__SHAPE__.dashboardUtils;

  const MMD_LABELS = {
    '1buy': '一买', '2buy': '二买', '3buy': '三买',
    'l2buy': '类二买', 'l3buy': '类三买',
    '1sell': '一卖', '2sell': '二卖', '3sell': '三卖',
    'l2sell': '类二卖', 'l3sell': '类三卖',
  };
  const BC_LABELS = { bi: '笔背驰', xd: '线段背驰', pz: '盘整背驰', qs: '趋势背驰' };
  const TREND_LABELS = { up: '上涨趋势', down: '下跌趋势' };

  function joinLabels(codes, mapping) {
    if (!codes) return null;
    const labels = codes.split('|').filter(Boolean).map((c) => mapping[c] || c);
    return labels.length ? labels.join('、') : null;
  }

  function dirColor(direction) {
    if (direction === 'up') return 'var(--red)';
    if (direction === 'down') return 'var(--green)';
    return 'var(--text)';
  }

  function recColor(rec) {
    if (/BUY/i.test(rec)) return 'var(--red)';
    if (/SELL/i.test(rec)) return 'var(--green)';
    return 'var(--text)';
  }

  function BottomCards() {
    const { sentiment, analyst, chanlun } = useDashboard();
    const mmdText = joinLabels(chanlun && chanlun.mmd, MMD_LABELS);
    const bcText = joinLabels(chanlun && chanlun.bc, BC_LABELS);

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
            缠论结构
            {chanlun && chanlun.dataDate && <span className="subtitle">{chanlun.dataDate} 数据</span>}
          </div>
          <div className="chanlun-grid">
            <div className="chanlun-item">
              <div className="label">当前笔</div>
              <div className="value" style={{ color: chanlun ? dirColor(chanlun.biDirection) : 'var(--text)' }}>
                {chanlun ? (chanlun.biDirection === 'up' ? '↑ 上涨' : '↓ 下跌') : '—'}
              </div>
            </div>
            <div className="chanlun-item">
              <div className="label">结构趋势</div>
              <div className="value" style={{ color: chanlun ? dirColor(chanlun.trend) : 'var(--text)' }}>
                {chanlun ? (TREND_LABELS[chanlun.trend] || '盘整延伸') : '—'}
              </div>
            </div>
            <div className="chanlun-item">
              <div className="label">中枢区间</div>
              <div className="value">{chanlun && chanlun.zsZD != null ? `${chanlun.zsZD}–${chanlun.zsZG}` : '—'}</div>
            </div>
            <div className="chanlun-item">
              <div className="label">最近买卖点</div>
              <div
                className="value"
                style={{ color: chanlun && mmdText ? (chanlun.mmd.includes('buy') ? 'var(--red)' : 'var(--green)') : 'var(--text)' }}
              >
                {chanlun ? (mmdText || '无') : '—'}
              </div>
            </div>
          </div>
          {chanlun && (
            <div className="analyst-meta">
              <span>
                最新笔 <strong>{(chanlun.biStart || '').slice(5)} 起 · {chanlun.biDone ? '已完成' : '进行中'}</strong>
              </span>
              <span className="analyst-votes">
                {chanlun.mmdDate && <>信号日 <strong>{chanlun.mmdDate.slice(5)}</strong> · </>}
                {bcText && <>背驰 <strong>{bcText}</strong> · </>}
                收盘 <strong>{chanlun.close}</strong>
              </span>
            </div>
          )}
        </div>
      </div>
    );
  }

  window.__SHAPE__.dashboardBottomCards = BottomCards;
})();
