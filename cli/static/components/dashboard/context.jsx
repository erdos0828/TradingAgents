(function () {
  const { createContext, useContext, useState, useMemo } = React;

  const DashboardContext = createContext(null);

  function DashboardProvider({ children }) {
    const [market, setMarket] = useState('a-share');
    const [activeHoldingIdx, setActiveHoldingIdx] = useState(0);

    const data = window.__SHAPE__.dashboardData;

    const indices = data.indices[market];
    const holdings = data.holdings[market];
    const portfolio = data.portfolio[market];
    const signals = data.signals[market];
    const sentiment = data.sentiment[market];
    const analyst = data.analyst[market];
    const financial = data.financial[market];
    const stockDetail = data.stockDetail[market];
    const tradingDays = data.tradingDays;
    const matrix = data.matrix;

    const activeHolding = useMemo(() => holdings[activeHoldingIdx] || holdings[0], [holdings, activeHoldingIdx]);

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
      financial,
      stockDetail,
      tradingDays,
      matrix,
      activeHolding,
    };

    return React.createElement(DashboardContext.Provider, { value }, children);
  }

  function useDashboard() {
    return useContext(DashboardContext);
  }

  window.__SHAPE__.dashboardContext = { DashboardProvider, useDashboard };
})();
