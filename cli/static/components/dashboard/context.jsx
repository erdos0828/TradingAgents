(function () {
  const { createContext, useContext, useState, useMemo, useEffect } = React;

  const DashboardContext = createContext(null);

  function DashboardProvider({ children }) {
    const [market, setMarket] = useState('a-share');
    const [activeHoldingIdx, setActiveHoldingIdx] = useState(0);
    const [livePortfolio, setLivePortfolio] = useState(null);
    const [stockData, setStockData] = useState(null);
    const [liveMatrix, setLiveMatrix] = useState(null);
    const [analysisData, setAnalysisData] = useState(null);
    // Default matrix baseline to yesterday (local time), since today's session
    // is usually incomplete and has no T+1 outcome yet.
    const [matrixDate, setMatrixDate] = useState(() => {
      const d = new Date();
      d.setDate(d.getDate() - 1);
      const mm = String(d.getMonth() + 1).padStart(2, '0');
      const dd = String(d.getDate()).padStart(2, '0');
      return `${d.getFullYear()}-${mm}-${dd}`;
    });

    // Fetch real portfolio overview from the backend; keep sample data on failure.
    useEffect(() => {
      let cancelled = false;
      fetch('/api/dashboard/portfolio')
        .then((res) => (res.ok ? res.json() : Promise.reject(new Error('HTTP ' + res.status))))
        .then((payload) => {
          if (cancelled || !payload || payload.error) return;
          setLivePortfolio(payload);
        })
        .catch((err) => {
          console.warn('[dashboard] portfolio API unavailable, using sample data:', err.message);
        });
      return () => { cancelled = true; };
    }, []);

    // Fetch the backtest matrix; refetch whenever the selected date changes.
    useEffect(() => {
      let cancelled = false;
      const url = '/api/dashboard/matrix' + (matrixDate ? '?date=' + encodeURIComponent(matrixDate) : '');
      fetch(url)
        .then((res) => (res.ok ? res.json() : Promise.reject(new Error('HTTP ' + res.status))))
        .then((payload) => {
          if (cancelled || !payload || payload.error || !payload.matrix) return;
          setLiveMatrix(payload);
        })
        .catch((err) => {
          console.warn('[dashboard] matrix API unavailable, using sample data:', err.message);
        });
      return () => { cancelled = true; };
    }, [matrixDate]);

    const data = window.__SHAPE__.dashboardData;

    const liveMarket = livePortfolio ? livePortfolio[market] : null;
    const indices = data.indices[market];
    const holdings = liveMarket && liveMarket.holdings.length ? liveMarket.holdings : data.holdings[market];
    const portfolio = liveMarket ? liveMarket.portfolio : data.portfolio[market];
    const signals = data.signals[market];
    const tradingDays = liveMatrix ? liveMatrix.tradingDays : data.tradingDays;
    const matrix = liveMatrix ? liveMatrix.matrix : data.matrix;

    const activeHolding = useMemo(() => holdings[activeHoldingIdx] || holdings[0], [holdings, activeHoldingIdx]);

    // Fetch candles + quote for the selected holding whenever its ticker changes.
    const activeTicker = activeHolding && activeHolding.ticker;
    useEffect(() => {
      if (!activeTicker) return;
      let cancelled = false;
      setStockData(null);
      fetch('/api/dashboard/stock/' + encodeURIComponent(activeTicker))
        .then((res) => (res.ok ? res.json() : Promise.reject(new Error('HTTP ' + res.status))))
        .then((payload) => {
          if (cancelled || !payload || payload.error || !payload.candles || !payload.candles.length) return;
          setStockData(payload);
        })
        .catch((err) => {
          console.warn('[dashboard] stock API unavailable for', activeTicker, ':', err.message);
        });
      return () => { cancelled = true; };
    }, [activeTicker]);

    const stockDetail = stockData
      ? {
          name: stockData.name,
          code: stockData.ticker,
          price: stockData.price,
          change: [stockData.changeAmount, stockData.changePercent].filter(Boolean).join(' '),
          up: stockData.up,
        }
      : data.stockDetail[market];

    // Fetch the report-based analysis cards (sentiment / analyst / chanlun)
    // whenever the selected holding changes; keep sample data on failure.
    useEffect(() => {
      if (!activeTicker) return undefined;
      let cancelled = false;
      setAnalysisData(null);
      fetch('/api/dashboard/analysis/' + encodeURIComponent(activeTicker))
        .then((res) => (res.ok ? res.json() : Promise.reject(new Error('HTTP ' + res.status))))
        .then((payload) => {
          if (cancelled || !payload || payload.error) return;
          setAnalysisData(payload);
        })
        .catch((err) => {
          console.warn('[dashboard] analysis API unavailable for', activeTicker, ':', err.message);
        });
      return () => { cancelled = true; };
    }, [activeTicker]);

    const sentiment = analysisData && analysisData.sentiment
      ? { ...analysisData.sentiment, reportDate: analysisData.reportDate }
      : data.sentiment[market];
    const analyst = analysisData && analysisData.analyst
      ? analysisData.analyst
      : data.analyst[market];
    // When the API responds but carries no chanlun payload (chanlun-core
    // missing or insufficient bars), keep null so the card shows placeholders
    // instead of falling back to sample data.
    const chanlun = analysisData
      ? analysisData.chanlun || null
      : data.chanlun[market];

    const setMarketAndReset = (nextMarket) => {
      setMarket(nextMarket);
      setActiveHoldingIdx(0);
    };

    const value = {
      market,
      setMarket: setMarketAndReset,
      activeHoldingIdx,
      setActiveHoldingIdx,
      indices,
      holdings,
      portfolio,
      signals,
      sentiment,
      analyst,
      chanlun,
      stockDetail,
      stockData,
      tradingDays,
      matrix,
      matrixDate,
      setMatrixDate,
      matrixDates: liveMatrix ? liveMatrix.availableDates || [] : [],
      activeHolding,
    };

    return React.createElement(DashboardContext.Provider, { value }, children);
  }

  function useDashboard() {
    return useContext(DashboardContext);
  }

  window.__SHAPE__.dashboardContext = { DashboardProvider, useDashboard };
})();
