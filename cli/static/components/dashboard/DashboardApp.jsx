(function () {
  const { DashboardProvider } = window.__SHAPE__.dashboardContext;
  const { DashboardLayout } = window.__SHAPE__.dashboardLayout;

  function RootApp() {
    return (
      <DashboardProvider>
        <DashboardLayout />
      </DashboardProvider>
    );
  }

  window.__SHAPE__.dashboardPages = { RootApp };
})();
