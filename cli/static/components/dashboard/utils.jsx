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
    if (sig === 'BUY') return 'signal-buy';
    if (sig === 'SELL') return 'signal-sell';
    if (sig === 'HOLD') return 'signal-hold';
    return 'signal-none';
  }

  function signalLabel(sig) {
    return { BUY: '买入', SELL: '卖出', HOLD: '持有' }[sig] || '—';
  }

  function signalBg(sig) {
    if (sig === 'BUY') return 'var(--red)';
    if (sig === 'SELL') return 'var(--green)';
    if (sig === 'HOLD') return 'var(--orange)';
    return 'transparent';
  }

  window.__SHAPE__.dashboardUtils = {
    formatNumber,
    generateSampleCandles,
    calculateMA,
    signalColor,
    signalLabel,
    signalBg,
  };
})();
