(function () {
  const { TopBar, WatchList, KLineChart, AnalysisTabs, PerformanceMatrix } = window.__SHAPE__;

  function AppLayout() {
    return (
      <div className="min-h-screen flex flex-col">
        <TopBar />

        <main className="flex-1 px-6 py-5 space-y-5 max-w-[1600px] mx-auto w-full">
          {/* upper row: watchlist + chart+tabs stack */}
          <div className="grid grid-cols-1 lg:grid-cols-[300px_1fr] gap-5 items-start">
            <div className="lg:sticky lg:top-4 lg:max-h-[calc(100vh-2rem)]">
              <WatchList />
            </div>
            <div className="space-y-5">
              <KLineChart />
              <AnalysisTabs />
            </div>
          </div>

          {/* bottom performance matrix */}
          <PerformanceMatrix />
        </main>

        <footer className="border-t border-brand-border px-6 py-4 flex flex-wrap items-center justify-between gap-3 text-[10px] font-mono-num text-brand-muted">
          <div className="flex items-center gap-3">
            <span className="tab-serif text-primary">— fin —</span>
            <span>本刊数据源自公开市场,静态排印,不构成投资建议。</span>
          </div>
          <div className="flex items-center gap-4">
            <span>© 2026 Ticker Foundry Research</span>
            <span>Set in DM Serif Display · IBM Plex</span>
          </div>
        </footer>
      </div>
    );
  }

  window.__SHAPE__.layout = { AppLayout };
})();
