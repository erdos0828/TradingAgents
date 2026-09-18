(function () {
  const { useDashboard } = window.__SHAPE__.dashboardContext;

  function SignalPanel() {
    const { signals } = useDashboard();

    return (
      <section className="card">
        <div className="card-title">
          动态信号流
          <span className="subtitle">实时异动</span>
        </div>
        <div className="signal-list">
          {signals.map((s, idx) => (
            <div className="signal-item" key={idx}>
              <div className="signal-time">{s.time}</div>
              <div className="signal-content">
                <div className="signal-title">
                  {s.title}
                  <span className={`signal-badge ${s.type === 'buy' ? 'buy' : s.type === 'sell' ? 'sell' : ''}`}>
                    {s.badge}
                  </span>
                </div>
                <div className="signal-desc">{s.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </section>
    );
  }

  window.__SHAPE__.dashboardSignalPanel = SignalPanel;
})();
