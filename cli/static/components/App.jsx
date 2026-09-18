(function () {
  const { AppProvider } = window.__SHAPE__.context;
  const { AppLayout } = window.__SHAPE__.layout;

  function RootApp() {
    return (
      <AppProvider>
        <AppLayout />
      </AppProvider>
    );
  }

  window.__SHAPE__.pages.RootApp = RootApp;
})();
