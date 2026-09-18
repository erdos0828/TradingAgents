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

  function calcEMA(candles, period) {
    const k = 2 / (period + 1);
    let prev = null;
    return candles.map((c) => {
      const ema = prev === null ? c.close : c.close * k + prev * (1 - k);
      prev = ema;
      return { time: c.time, value: ema };
    });
  }

  // MACD (12, 26, 9), CN-market convention: bar = (DIF - DEA) * 2.
  function calcMACD(candles, fast = 12, slow = 26, signal = 9) {
    const emaFast = calcEMA(candles, fast);
    const emaSlow = calcEMA(candles, slow);
    const dif = candles.map((c, i) => ({
      time: c.time,
      value: emaFast[i].value - emaSlow[i].value,
    }));
    const k = 2 / (signal + 1);
    let prev = null;
    const dea = dif.map((d) => {
      const v = prev === null ? d.value : d.value * k + prev * (1 - k);
      prev = v;
      return { time: d.time, value: v };
    });
    const histogram = dif.map((d, i) => {
      const diff = d.value - dea[i].value;
      return {
        time: d.time,
        value: diff * 2,
        color: diff >= 0 ? '#ef4444' : '#10b981',
      };
    });
    return { dif, dea, histogram };
  }

  // KDJ (9, 3, 3): RSV double-smoothed by SMA(x, 3, 1); J = 3K - 2D.
  function calcKDJ(candles, n = 9) {
    const k = [];
    const d = [];
    const j = [];
    let prevK = 50;
    let prevD = 50;
    for (let i = 0; i < candles.length; i++) {
      const first = Math.max(0, i - n + 1);
      let hh = -Infinity;
      let ll = Infinity;
      for (let t = first; t <= i; t++) {
        hh = Math.max(hh, candles[t].high);
        ll = Math.min(ll, candles[t].low);
      }
      const rsv = hh === ll ? 50 : ((candles[i].close - ll) / (hh - ll)) * 100;
      const curK = (prevK * 2 + rsv) / 3;
      const curD = (prevD * 2 + curK) / 3;
      const curJ = curK * 3 - curD * 2;
      k.push({ time: candles[i].time, value: curK });
      d.push({ time: candles[i].time, value: curD });
      j.push({ time: candles[i].time, value: curJ });
      prevK = curK;
      prevD = curD;
    }
    return { k, d, j };
  }

  // RSI with Wilder smoothing (equivalent to CN-market SMA(x, n, 1)).
  function calcRSI(candles, period) {
    const out = [];
    let avgGain = null;
    let avgLoss = null;
    for (let i = 1; i < candles.length; i++) {
      const change = candles[i].close - candles[i - 1].close;
      const gain = Math.max(change, 0);
      const loss = Math.max(-change, 0);
      if (avgGain === null) {
        avgGain = gain;
        avgLoss = loss;
      } else {
        avgGain = (avgGain * (period - 1) + gain) / period;
        avgLoss = (avgLoss * (period - 1) + loss) / period;
      }
      const rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
      out.push({ time: candles[i].time, value: rsi });
    }
    return out;
  }

  // BOLL (20, 2): population standard deviation, CN-market style.
  function calcBOLL(candles, n = 20, width = 2) {
    const mid = [];
    const up = [];
    const low = [];
    for (let i = n - 1; i < candles.length; i++) {
      let sum = 0;
      for (let t = i - n + 1; t <= i; t++) sum += candles[t].close;
      const m = sum / n;
      let sq = 0;
      for (let t = i - n + 1; t <= i; t++) sq += (candles[t].close - m) * (candles[t].close - m);
      const sd = Math.sqrt(sq / n);
      mid.push({ time: candles[i].time, value: m });
      up.push({ time: candles[i].time, value: m + width * sd });
      low.push({ time: candles[i].time, value: m - width * sd });
    }
    return { mid, up, low };
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
    calcEMA,
    calcMACD,
    calcKDJ,
    calcRSI,
    calcBOLL,
    signalColor,
    signalLabel,
    signalBg,
    signalRank,
  };
})();
