(function () {
  const { useDashboard } = window.__SHAPE__.dashboardContext;

  function Header() {
    const { market, setMarket, indices } = useDashboard();

    return (
      <header className="header">
        <div className="header-left">
          <div className="logo">
            <div className="logo-icon">智</div>
            <span>智投工作台</span>
          </div>
          <div className="indices">
            {indices.map((idx) => (
              <div className="index-item" key={idx.name}>
                <span className="index-name">{idx.name}</span>
                <span className="index-value">{idx.value}</span>
                <span className={`index-change ${idx.up ? 'up' : 'down'}`}>{idx.change}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="market-toggle">
          <button className={market === 'a-share' ? 'active' : ''} onClick={() => setMarket('a-share')}>
            A股市场
          </button>
          <button className={market === 'us' ? 'active' : ''} onClick={() => setMarket('us')}>
            美股市场
          </button>
        </div>
      </header>
    );
  }

  window.__SHAPE__.dashboardHeader = Header;
})();
