(function () {
  const A_STOCKS = [
    {
      code: '600519', name: '贵州茅台', currency: 'CNY',
      prev: 1788.00, change: 12.50, changePct: 0.70,
      ma5: 1815.00, ma10: 1762.00, ma20: 1740.00,
      signal: 'HOLD',
      sentiment: 8.5, bullPct: 68, socialHeat: 78.5,
      volume: '3.24M', turnover: '58.2亿',
      high52: 2098.00, low52: 1428.00,
    },
    {
      code: '300750', name: '宁德时代', currency: 'CNY',
      prev: 192.30, change: 2.28, changePct: 1.20,
      ma5: 189.40, ma10: 195.10, ma20: 202.30,
      signal: 'BUY',
      sentiment: 7.2, bullPct: 74, socialHeat: 82.3,
      volume: '12.7M', turnover: '24.4亿',
      high52: 260.00, low52: 152.10,
    },
    {
      code: '600036', name: '招商银行', currency: 'CNY',
      prev: 32.50, change: -0.15, changePct: -0.45,
      ma5: 32.80, ma10: 33.20, ma20: 33.55,
      signal: 'HOLD',
      sentiment: 6.4, bullPct: 52, socialHeat: 44.2,
      volume: '48.2M', turnover: '15.6亿',
      high52: 40.10, low52: 28.90,
    },
    {
      code: '002594', name: '比亚迪', currency: 'CNY',
      prev: 243.80, change: 2.18, changePct: 0.90,
      ma5: 240.10, ma10: 245.80, ma20: 251.30,
      signal: 'BUY',
      sentiment: 7.8, bullPct: 71, socialHeat: 88.6,
      volume: '18.4M', turnover: '44.8亿',
      high52: 289.00, low52: 195.40,
    },
    {
      code: '601318', name: '中国平安', currency: 'CNY',
      prev: 45.88, change: 0.11, changePct: 0.25,
      ma5: 45.60, ma10: 45.20, ma20: 44.80,
      signal: 'HOLD',
      sentiment: 6.8, bullPct: 58, socialHeat: 41.7,
      volume: '26.1M', turnover: '11.9亿',
      high52: 52.30, low52: 38.20,
    },
    {
      code: '000858', name: '五粮液', currency: 'CNY',
      prev: 148.30, change: -1.32, changePct: -0.88,
      ma5: 150.80, ma10: 152.40, ma20: 154.10,
      signal: 'SELL',
      sentiment: 5.4, bullPct: 42, socialHeat: 56.2,
      volume: '8.4M', turnover: '12.5亿',
      high52: 178.00, low52: 132.50,
    },
    {
      code: '600030', name: '中信证券', currency: 'CNY',
      prev: 24.16, change: 0.28, changePct: 1.17,
      ma5: 23.80, ma10: 23.42, ma20: 23.10,
      signal: 'BUY',
      sentiment: 7.4, bullPct: 66, socialHeat: 62.3,
      volume: '54.6M', turnover: '13.2亿',
      high52: 28.50, low52: 19.80,
    },
    {
      code: '600276', name: '恒瑞医药', currency: 'CNY',
      prev: 42.85, change: -0.19, changePct: -0.44,
      ma5: 43.20, ma10: 43.60, ma20: 44.10,
      signal: 'HOLD',
      sentiment: 6.0, bullPct: 48, socialHeat: 38.9,
      volume: '10.2M', turnover: '4.4亿',
      high52: 52.00, low52: 38.10,
    },
  ];

  const US_STOCKS = [
    {
      code: 'NVDA', name: 'NVIDIA', currency: 'USD',
      prev: 142.80, change: 3.42, changePct: 2.45,
      ma5: 140.10, ma10: 138.20, ma20: 135.60,
      signal: 'BUY',
      sentiment: 8.9, bullPct: 82, socialHeat: 94.2,
      volume: '284M', turnover: '$40.6B',
      high52: 152.00, low52: 78.20,
    },
    {
      code: 'AAPL', name: 'Apple Inc.', currency: 'USD',
      prev: 224.60, change: 1.12, changePct: 0.50,
      ma5: 223.20, ma10: 221.80, ma20: 220.50,
      signal: 'HOLD',
      sentiment: 7.2, bullPct: 62, socialHeat: 68.4,
      volume: '52M', turnover: '$11.7B',
      high52: 237.50, low52: 168.30,
    },
    {
      code: 'MSFT', name: 'Microsoft', currency: 'USD',
      prev: 418.30, change: 4.62, changePct: 1.12,
      ma5: 415.20, ma10: 412.80, ma20: 408.40,
      signal: 'BUY',
      sentiment: 7.8, bullPct: 71, socialHeat: 72.1,
      volume: '18M', turnover: '$7.5B',
      high52: 468.00, low52: 362.90,
    },
    {
      code: 'TSLA', name: 'Tesla', currency: 'USD',
      prev: 248.20, change: -2.14, changePct: -0.85,
      ma5: 251.30, ma10: 254.80, ma20: 258.40,
      signal: 'SELL',
      sentiment: 5.8, bullPct: 44, socialHeat: 91.7,
      volume: '92M', turnover: '$22.9B',
      high52: 299.00, low52: 138.80,
    },
    {
      code: 'GOOGL', name: 'Alphabet', currency: 'USD',
      prev: 178.50, change: 1.98, changePct: 1.12,
      ma5: 176.80, ma10: 175.10, ma20: 172.60,
      signal: 'BUY',
      sentiment: 7.4, bullPct: 68, socialHeat: 66.8,
      volume: '22M', turnover: '$3.9B',
      high52: 193.20, low52: 141.30,
    },
    {
      code: 'AMZN', name: 'Amazon', currency: 'USD',
      prev: 194.20, change: -0.42, changePct: -0.22,
      ma5: 194.80, ma10: 193.60, ma20: 191.80,
      signal: 'HOLD',
      sentiment: 6.9, bullPct: 58, socialHeat: 55.3,
      volume: '38M', turnover: '$7.4B',
      high52: 201.20, low52: 138.90,
    },
  ];

  function seededRandom(seed) {
    let s = seed;
    return () => {
      s = (s * 9301 + 49297) % 233280;
      return s / 233280;
    };
  }

  function buildKLine(stock) {
    const rand = seededRandom(stock.code.split('').reduce((a, c) => a + c.charCodeAt(0), 0));
    const bars = [];
    let base = stock.prev * 0.88;
    for (let i = 0; i < 60; i++) {
      const drift = (rand() - 0.48) * base * 0.028;
      const open = base;
      const close = Math.max(open + drift, open * 0.94);
      const wickHi = Math.max(open, close) + rand() * base * 0.012;
      const wickLo = Math.min(open, close) - rand() * base * 0.012;
      bars.push({ open, close, high: wickHi, low: wickLo, up: close >= open });
      base = close;
    }
    const scale = stock.prev / bars[bars.length - 1].close;
    bars.forEach(b => {
      b.open *= scale; b.close *= scale; b.high *= scale; b.low *= scale;
    });
    return bars;
  }

  // 15 trading days matrix. Each entry: signal + outcome (up/down/flat/none).
  const TRADING_DAYS = [
    { date: '09-05', dow: '五' }, { date: '09-04', dow: '四' }, { date: '09-03', dow: '三' },
    { date: '09-02', dow: '二' }, { date: '09-01', dow: '一' }, { date: '08-29', dow: '五' },
    { date: '08-28', dow: '四' }, { date: '08-27', dow: '三' }, { date: '08-26', dow: '二' },
    { date: '08-25', dow: '一' }, { date: '08-22', dow: '五' }, { date: '08-21', dow: '四' },
    { date: '08-20', dow: '三' }, { date: '08-19', dow: '二' }, { date: '08-18', dow: '一' },
  ];

  function buildMatrixRow(stockCode, seedOffset) {
    const rand = seededRandom(stockCode.charCodeAt(0) * 13 + seedOffset);
    return TRADING_DAYS.map((day, i) => {
      const r = rand();
      let signal, t1, t2;
      if (r < 0.15) { signal = null; t1 = 0; t2 = 0; }
      else if (r < 0.4) { signal = 'BUY'; t1 = (rand() - 0.3) * 3; t2 = t1 + (rand() - 0.4) * 2; }
      else if (r < 0.7) { signal = 'HOLD'; t1 = (rand() - 0.5) * 1.6; t2 = t1 + (rand() - 0.5) * 1.2; }
      else { signal = 'SELL'; t1 = (rand() - 0.55) * 2.4; t2 = t1 + (rand() - 0.55) * 2; }
      return { day: day.date, dow: day.dow, signal, t1: Number(t1.toFixed(2)), t2: Number(t2.toFixed(2)) };
    });
  }

  const MATRIX = {
    '600519': buildMatrixRow('600519', 7),
    '300750': buildMatrixRow('300750', 11),
    '600036': buildMatrixRow('600036', 17),
    '002594': buildMatrixRow('002594', 23),
    '601318': buildMatrixRow('601318', 29),
    '000858': buildMatrixRow('000858', 37),
    '600030': buildMatrixRow('600030', 43),
    '600276': buildMatrixRow('600276', 47),
    'NVDA':   buildMatrixRow('NVDA',   51),
    'AAPL':   buildMatrixRow('AAPL',   57),
    'MSFT':   buildMatrixRow('MSFT',   61),
    'TSLA':   buildMatrixRow('TSLA',   67),
    'GOOGL':  buildMatrixRow('GOOGL',  71),
    'AMZN':   buildMatrixRow('AMZN',   73),
  };

  const REPORTS = {
    '600519': {
      verdict: 'HOLD',
      verdictLabel: '持有',
      thesis: '外部宏观扰动与消费景气缓步修复形成对冲，短线以震荡整理为主。',
      conservative: '考虑到外部宏观数据以及库存周期尚未见底，赞同风控意见，防守重于进攻。',
      aggressive: '消费复苏趋势明确，白酒龙头具备强定价权，当前估值已具备极高安全边际，回撤即机会。',
      neutral: '维持核心仓位，等待旺季动销与批价共振信号，再择机加仓。',
      risks: [
        '批价短期承压，若跌破 2450 元支撑需警惕情绪转弱。',
        '宏观消费数据低于预期，可选消费板块可能整体估值下移。',
        '经销商库存去化速度慢于往年，会拖累三季度收入确认节奏。',
      ],
      catalysts: [
        '中秋、国庆双节动销数据超预期。',
        '公司分红或回购加码，提升 ROE 与股东回报预期。',
        '外资持续增持消费核心资产，情绪面回暖。',
      ],
      financial: {
        revenue: '150.6亿',
        revenueYoy: '+18.4%',
        netProfit: '76.8亿',
        netProfitYoy: '+16.2%',
        gross: '92.1%',
        roe: '31.4%',
        pe: 24.6, pb: 8.9, eps: 72.68, dps: 30.88,
      },
      analysts: { buy: 24, hold: 6, sell: 1, target: 2168.00, consensus: '增持' },
      technical: {
        trend: '上行',
        rsi: 54.2,
        macd: '金叉初期',
        kdj: '低位钝化',
        support: 1720.00,
        resistance: 1852.00,
      },
    },
    '300750': {
      verdict: 'BUY',
      verdictLabel: '买入',
      thesis: '海外储能订单加速兑现，动力电池份额企稳回升，估值仍在历史中枢下轨。',
      conservative: '短期已有一定涨幅，建议分批建仓，避免情绪追高。',
      aggressive: '储能第二曲线放量，海外客户结构改善，具备戴维斯双击潜力。',
      neutral: '建议关注下一份财报的储能业务收入占比与毛利率表现。',
      risks: [
        '欧美电动车渗透率放缓，动力电池订单存在阶段性波动。',
        '碳酸锂价格反弹将短期压缩毛利。',
        '海外贸易政策不确定性，需关注美国 IRA 补贴细则调整。',
      ],
      catalysts: [
        '欧洲储能签单大规模落地。',
        '固态电池样品送样或量产进度超预期。',
        '下游车企新车型放量，带动电池需求回升。',
      ],
      financial: {
        revenue: '826.5亿',
        revenueYoy: '-11.9%',
        netProfit: '105.3亿',
        netProfitYoy: '+26.4%',
        gross: '26.5%',
        roe: '17.8%',
        pe: 17.8, pb: 3.1, eps: 4.86, dps: 1.20,
      },
      analysts: { buy: 32, hold: 4, sell: 0, target: 245.00, consensus: '强烈推荐' },
      technical: {
        trend: '底部回升',
        rsi: 62.4,
        macd: '零轴上方',
        kdj: '中位',
        support: 178.00,
        resistance: 210.00,
      },
    },
  };

  function getReport(code) {
    if (REPORTS[code]) return REPORTS[code];
    // fallback report skeleton
    return {
      verdict: 'HOLD',
      verdictLabel: '持有',
      thesis: '暂无独立深度覆盖，沿用行业中性判断。',
      conservative: '缺乏催化剂，保持观望。',
      aggressive: '关注同板块龙头联动信号。',
      neutral: '等待更清晰的趋势确认。',
      risks: ['板块整体估值扰动。', '流动性收紧。', '业绩不及预期。'],
      catalysts: ['行业景气拐点。', '政策利好释放。', '资金面转暖。'],
      financial: {
        revenue: '—', revenueYoy: '—',
        netProfit: '—', netProfitYoy: '—',
        gross: '—', roe: '—',
        pe: '—', pb: '—', eps: '—', dps: '—',
      },
      analysts: { buy: 10, hold: 12, sell: 2, target: 0, consensus: '中性' },
      technical: { trend: '震荡', rsi: 50, macd: '粘连', kdj: '中位', support: 0, resistance: 0 },
    };
  }

  // Latest snapshot day + 15 historical trading days.
  // idx 0 -> today's post-close; idx 1..15 map to MATRIX[0..14].
  const DATES = [
    { date: '2026-09-07', short: '09-07', dow: '一', isLatest: true },
    ...TRADING_DAYS.map(d => ({ date: `2026-${d.date}`, short: d.date, dow: d.dow, isLatest: false })),
  ];

  // Reverse-derive a per-stock snapshot for the target date index.
  // Uses the historical matrix's t1 column as the daily change to walk price back in time.
  function getStockAsOf(stock, dateIdx) {
    if (!dateIdx) return { ...stock, dateIdx: 0 };
    const row = MATRIX[stock.code];
    if (!row) return { ...stock, dateIdx };

    // Walk price back day-by-day. row[i].t1 represents that historical day's realised move.
    let price = stock.prev;
    for (let i = 0; i < dateIdx; i++) {
      const pct = (row[i] && typeof row[i].t1 === 'number') ? row[i].t1 : 0;
      price = price / (1 + pct / 100);
    }
    const dayEntry = row[dateIdx - 1] || {};
    const changePct = typeof dayEntry.t1 === 'number' ? dayEntry.t1 : 0;
    const change = price * changePct / 100;
    const signal = dayEntry.signal || stock.signal;

    // Drift MAs slightly for a plausible historical read.
    const drift = 1 - dateIdx * 0.004;
    return {
      ...stock,
      dateIdx,
      prev: price,
      change,
      changePct,
      signal,
      ma5:  stock.ma5  * drift,
      ma10: stock.ma10 * drift * 0.995,
      ma20: stock.ma20 * drift * 0.99,
    };
  }

  window.__SHAPE__.mocks = {
    A_STOCKS, US_STOCKS, MATRIX, TRADING_DAYS, DATES,
    buildKLine, getReport, getStockAsOf,
  };

  window.__SHAPE__.utils = {
    fmtNum(v, digits = 2) {
      if (typeof v !== 'number') return v;
      return v.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    },
    fmtPct(v, digits = 2) {
      if (typeof v !== 'number') return v;
      const sign = v > 0 ? '+' : '';
      return `${sign}${v.toFixed(digits)}%`;
    },
    signalColor(sig) {
      if (sig === 'BUY') return 'signal-buy';
      if (sig === 'SELL') return 'signal-sell';
      if (sig === 'HOLD') return 'signal-hold';
      return 'signal-none';
    },
    signalLabel(sig) {
      return { BUY: '买入', SELL: '卖出', HOLD: '持有' }[sig] || '—';
    },
  };
})();
