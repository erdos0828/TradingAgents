(function () {
  function seededRandom(seed) {
    let s = seed;
    return () => {
      s = (s * 9301 + 49297) % 233280;
      return s / 233280;
    };
  }

  const TRADING_DAYS = [
    { date: '09-05', dow: '五' }, { date: '09-04', dow: '四' }, { date: '09-03', dow: '三' },
    { date: '09-02', dow: '二' }, { date: '09-01', dow: '一' }, { date: '08-29', dow: '五' },
    { date: '08-28', dow: '四' }, { date: '08-27', dow: '三' }, { date: '08-26', dow: '二' },
    { date: '08-25', dow: '一' }, { date: '08-22', dow: '五' }, { date: '08-21', dow: '四' },
    { date: '08-20', dow: '三' }, { date: '08-19', dow: '二' }, { date: '08-18', dow: '一' },
  ];

  function buildMatrixRow(stockCode, seedOffset) {
    const rand = seededRandom(stockCode.charCodeAt(0) * 13 + seedOffset);
    return TRADING_DAYS.map((day) => {
      const r = rand();
      let signal, t1, t2;
      if (r < 0.15) { signal = null; t1 = 0; t2 = 0; }
      else if (r < 0.4) { signal = 'BUY'; t1 = (rand() - 0.3) * 3; t2 = t1 + (rand() - 0.4) * 2; }
      else if (r < 0.7) { signal = 'HOLD'; t1 = (rand() - 0.5) * 1.6; t2 = t1 + (rand() - 0.5) * 1.2; }
      else { signal = 'SELL'; t1 = (rand() - 0.55) * 2.4; t2 = t1 + (rand() - 0.55) * 2; }
      return { day: day.date, dow: day.dow, signal, t1: Number(t1.toFixed(2)), t2: Number(t2.toFixed(2)) };
    });
  }

  const A_HOLDINGS = [
    { name: '贵州茅台', code: '600519', price: '1,768.00', change: '+0.70%', up: true, weight: '14.7%', quantity: 100, costPrice: 1720.0, marketValue: 176800.0, dailyPnl: 1229.1, dailyPnlPercent: '+0.70%', positionPnl: 4800.0, positionPnlPercent: '+2.79%' },
    { name: '宁德时代', code: '300750', price: '192.30', change: '+1.43%', up: true, weight: '12.8%', quantity: 500, costPrice: 178.5, marketValue: 96150.0, dailyPnl: 1355.0, dailyPnlPercent: '+1.43%', positionPnl: 6900.0, positionPnlPercent: '+7.73%' },
    { name: '招商银行', code: '600036', price: '32.50', change: '-0.61%', up: false, weight: '10.5%', quantity: 3000, costPrice: 34.8, marketValue: 97500.0, dailyPnl: -600.0, dailyPnlPercent: '-0.61%', positionPnl: -6900.0, positionPnlPercent: '-6.61%' },
    { name: '中国平安', code: '601318', price: '45.90', change: '+0.22%', up: true, weight: '9.2%', quantity: 2000, costPrice: 44.1, marketValue: 91800.0, dailyPnl: 200.0, dailyPnlPercent: '+0.22%', positionPnl: 3600.0, positionPnlPercent: '+4.08%' },
    { name: '比亚迪', code: '002594', price: '245.80', change: '+1.12%', up: true, weight: '8.4%', quantity: 300, costPrice: 252.0, marketValue: 73740.0, dailyPnl: 816.0, dailyPnlPercent: '+1.12%', positionPnl: -1860.0, positionPnlPercent: '-2.46%' },
  ];

  const US_HOLDINGS = [
    { name: 'Apple', code: 'AAPL', price: '178.35', change: '+0.85%', up: true, weight: '18.2%', quantity: 150, costPrice: 168.2, marketValue: 26752.5, dailyPnl: 225.0, dailyPnlPercent: '+0.85%', positionPnl: 1522.5, positionPnlPercent: '+6.04%' },
    { name: 'Microsoft', code: 'MSFT', price: '332.40', change: '+0.32%', up: true, weight: '16.5%', quantity: 80, costPrice: 320.0, marketValue: 26592.0, dailyPnl: 84.8, dailyPnlPercent: '+0.32%', positionPnl: 992.0, positionPnlPercent: '+3.88%' },
    { name: 'Tesla', code: 'TSLA', price: '245.60', change: '-1.20%', up: false, weight: '12.1%', quantity: 60, costPrice: 268.0, marketValue: 14736.0, dailyPnl: -178.8, dailyPnlPercent: '-1.20%', positionPnl: -1344.0, positionPnlPercent: '-8.36%' },
    { name: 'NVIDIA', code: 'NVDA', price: '460.15', change: '+1.45%', up: true, weight: '14.3%', quantity: 50, costPrice: 415.0, marketValue: 23007.5, dailyPnl: 328.0, dailyPnlPercent: '+1.45%', positionPnl: 2257.5, positionPnlPercent: '+10.88%' },
    { name: 'BABA', code: 'BABA', price: '88.20', change: '-0.55%', up: false, weight: '9.8%', quantity: 400, costPrice: 92.5, marketValue: 35280.0, dailyPnl: -196.0, dailyPnlPercent: '-0.55%', positionPnl: -1720.0, positionPnlPercent: '-4.65%' },
  ];

  const A_SIGNALS = [
    { time: '10:32', title: '贵州茅台 (600519)', desc: '突破MA5压力位，成交量放大', badge: '买入', type: 'buy' },
    { time: '10:28', title: '中信证券 (600030)', desc: '触及前期高点，MACD顶背离', badge: '卖出', type: 'sell' },
    { time: '10:15', title: '五粮液 (000858)', desc: 'RSI进入超买区间，异动提示', badge: '卖出', type: 'sell' },
    { time: '10:05', title: '迈瑞医疗 (300760)', desc: '多头主力净流入，趋势金叉', badge: '买入', type: 'buy' },
    { time: '09:48', title: '平安银行 (000001)', desc: '跌破支撑位置，空头排列', badge: '卖出', type: 'sell' },
    { time: '09:32', title: '恒瑞医药 (600276)', desc: '开盘分时急跌，大单抛售', badge: '卖出', type: 'sell' },
  ];

  const US_SIGNALS = [
    { time: '09:30', title: 'AAPL', desc: 'Gap up on volume, RSI 65', badge: '买入', type: 'buy' },
    { time: '09:28', title: 'TSLA', desc: 'Break below 20-day MA', badge: '卖出', type: 'sell' },
    { time: '09:15', title: 'NVDA', desc: 'New high on AI momentum', badge: '买入', type: 'buy' },
    { time: '09:05', title: 'MSFT', desc: 'Consolidation near resistance', badge: '中性', type: 'neutral' },
  ];

  const ALL_HOLDINGS = [...A_HOLDINGS, ...US_HOLDINGS];
  const MATRIX = {};
  ALL_HOLDINGS.forEach((h, idx) => {
    MATRIX[h.code] = buildMatrixRow(h.code, 7 + idx * 6);
  });

  const sampleData = {
    tradingDays: TRADING_DAYS,
    matrix: MATRIX,
    indices: {
      'a-share': [
        { name: '上证指数', value: '3,150.25', change: '+0.50%', up: true },
        { name: '深证成指', value: '10,240.10', change: '+0.62%', up: true },
        { name: '创业板指', value: '1,850.80', change: '+0.75%', up: true },
      ],
      'us': [
        { name: '道琼斯', value: '34,520.18', change: '-0.23%', up: false },
        { name: '纳斯达克', value: '13,890.42', change: '+0.45%', up: true },
        { name: '标普500', value: '4,450.32', change: '+0.12%', up: true },
      ]
    },
    holdings: {
      'a-share': A_HOLDINGS,
      'us': US_HOLDINGS,
    },
    portfolio: {
      'a-share': { total: '¥1,284,530.66', changeAmount: '+¥8,320.45', changePercent: '+0.65%', up: true },
      'us': { total: '$245,320.18', changeAmount: '+$1,245.60', changePercent: '+0.51%', up: true },
    },
    signals: {
      'a-share': A_SIGNALS,
      'us': US_SIGNALS,
    },
    sentiment: {
      'a-share': { score: '8.5', label: '极度贪婪', angle: 72 },
      'us': { score: '6.2', label: '贪婪', angle: 36 },
    },
    analyst: {
      'a-share': { bull: 68, bear: 32 },
      'us': { bull: 55, bear: 45 },
    },
    chanlun: {
      'a-share': { dataDate: '2026-09-09', close: 1768.0, biDirection: 'up', biDone: false, biStart: '2026-09-01', trend: 'up', mmd: '3buy', mmdDate: '2026-08-28', bc: null, zsZD: 1720.5, zsZG: 1780.2 },
      'us': { dataDate: '2026-09-09', close: 178.35, biDirection: 'up', biDone: false, biStart: '2026-09-04', trend: 'up', mmd: null, mmdDate: null, bc: 'pz', zsZD: 172.1, zsZG: 181.4 },
    },
    stockDetail: {
      'a-share': { name: '贵州茅台', code: '600519.SH', price: '1,768.00', change: '+12.30 (+0.70%)', up: true },
      'us': { name: 'Apple', code: 'AAPL', price: '$178.35', change: '+$1.50 (+0.85%)', up: true },
    }
  };

  window.__SHAPE__.dashboardData = sampleData;
})();
