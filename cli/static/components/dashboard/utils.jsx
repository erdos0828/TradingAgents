(function () {
  function formatNumber(n) {
    return Number(n).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function generateSampleCandles(market) {
    const data = [];
    let base = market === 'a-share' ? 1700 : 170;
    let date = new Date(2026, 7, 1);
    for (let i = 0; i < 60; i++) {
      const change = (Math.random() - 0.48) * base * 0.02;
      const open = base;
      const close = base + change;
      const high = Math.max(open, close) + Math.random() * base * 0.01;
      const low = Math.min(open, close) - Math.random() * base * 0.01;
      data.push({
        time: date.toISOString().split('T')[0],
        open: parseFloat(open.toFixed(2)),
        high: parseFloat(high.toFixed(2)),
        low: parseFloat(low.toFixed(2)),
        close: parseFloat(close.toFixed(2)),
      });
      base = close;
      date.setDate(date.getDate() + 1);
    }
    return data;
  }

  function calculateMA(candles, period) {
    const ma = [];
    for (let i = 0; i < candles.length; i++) {
      if (i < period - 1) continue;
      let sum = 0;
      for (let j = 0; j < period; j++) {
        sum += candles[i - j].close;
      }
      ma.push({
        time: candles[i].time,
        value: parseFloat((sum / period).toFixed(2)),
      });
    }
    return ma;
  }

  function signalColor(sig) {
    if (sig === 'BUY' || sig === 'Buy') return 'signal-buy';
    if (sig === 'SELL' || sig === 'Sell') return 'signal-sell';
    if (sig === 'HOLD' || sig === 'Hold') return 'signal-hold';
    if (sig === 'OVERWEIGHT' || sig === 'Overweight') return 'signal-overweight';
    if (sig === 'UNDERWEIGHT' || sig === 'Underweight') return 'signal-underweight';
    return 'signal-none';
  }

  function signalLabel(sig) {
    return {
      BUY: '买入', Buy: '买入',
      SELL: '卖出', Sell: '卖出',
      HOLD: '持有', Hold: '持有',
      OVERWEIGHT: '增持', Overweight: '增持',
      UNDERWEIGHT: '减持', Underweight: '减持',
    }[sig] || '—';
  }

  function signalBg(sig) {
    if (sig === 'BUY' || sig === 'Buy') return 'var(--red)';
    if (sig === 'SELL' || sig === 'Sell') return 'var(--green)';
    if (sig === 'HOLD' || sig === 'Hold') return 'var(--orange)';
    if (sig === 'OVERWEIGHT' || sig === 'Overweight') return 'var(--red)';
    if (sig === 'UNDERWEIGHT' || sig === 'Underweight') return 'var(--green)';
    return 'transparent';
  }

  // Five-level rating rank used for the matrix letter badge (strongest -> weakest).
  function signalRank(sig) {
    const ranks = {
      Buy: 2, BUY: 2, Overweight: 1, OVERWEIGHT: 1,
      Hold: 0, HOLD: 0,
      Underweight: -1, UNDERWEIGHT: -1, Sell: -2, SELL: -2,
    };
    return ranks[sig] === undefined ? null : ranks[sig];
  }

  window.__SHAPE__.dashboardUtils = {
    formatNumber,
    generateSampleCandles,
    calculateMA,
    signalColor,
    signalLabel,
    signalBg,
    signalRank,
  };
})();
