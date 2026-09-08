(function () {
  const Header = window.__SHAPE__.dashboardHeader;
  const PortfolioPanel = window.__SHAPE__.dashboardPortfolioPanel;
  const StockDetailPanel = window.__SHAPE__.dashboardStockDetailPanel;
  const SignalPanel = window.__SHAPE__.dashboardSignalPanel;
  const BottomCards = window.__SHAPE__.dashboardBottomCards;
  const PerformanceMatrix = window.__SHAPE__.dashboardPerformanceMatrix;

  function DashboardLayout() {
    return (
      <>
        <Header />
        <main className="main">
          <PortfolioPanel />
          <StockDetailPanel />
          <SignalPanel />
          <BottomCards />
          <PerformanceMatrix />
        </main>
      </>
    );
  }

  window.__SHAPE__.dashboardLayout = { DashboardLayout };
})();
