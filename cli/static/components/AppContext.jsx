(function () {
  const { createContext, useContext, useState, useMemo } = React;

  const AppContext = createContext(null);

  function AppProvider({ children }) {
    const [market, setMarket] = useState('A'); // 'A' | 'US'
    const [activeCode, setActiveCode] = useState('600519');
    const [activeTab, setActiveTab] = useState('core'); // core | sentiment | analyst | financial | risk | technical
    const [hoverCell, setHoverCell] = useState(null);
    const [activeDateIdx, setActiveDateIdx] = useState(0); // 0 = latest, 1..15 = historical

    const dates = window.__SHAPE__.mocks.DATES;
    const activeDate = dates[activeDateIdx] || dates[0];

    const rawStocks = useMemo(() => {
      return market === 'A' ? window.__SHAPE__.mocks.A_STOCKS : window.__SHAPE__.mocks.US_STOCKS;
    }, [market]);

    const stocks = useMemo(() => {
      const { getStockAsOf } = window.__SHAPE__.mocks;
      return rawStocks.map(s => getStockAsOf(s, activeDateIdx));
    }, [rawStocks, activeDateIdx]);

    const activeStock = useMemo(() => {
      return stocks.find(s => s.code === activeCode) || stocks[0];
    }, [stocks, activeCode]);

    // when switching markets, reset activeCode if the code no longer exists in the new market
    React.useEffect(() => {
      if (!rawStocks.find(s => s.code === activeCode)) {
        setActiveCode(rawStocks[0].code);
      }
    }, [market]);

    const prevDate = () => setActiveDateIdx(i => Math.min(dates.length - 1, i + 1));
    const nextDate = () => setActiveDateIdx(i => Math.max(0, i - 1));
    const jumpLatest = () => setActiveDateIdx(0);

    const value = {
      market, setMarket,
      activeCode, setActiveCode,
      activeTab, setActiveTab,
      hoverCell, setHoverCell,
      stocks, activeStock,
      dates, activeDateIdx, setActiveDateIdx, activeDate,
      prevDate, nextDate, jumpLatest,
    };

    return React.createElement(AppContext.Provider, { value }, children);
  }

  function useApp() {
    return useContext(AppContext);
  }

  window.__SHAPE__.context = { AppProvider, useApp };
})();
