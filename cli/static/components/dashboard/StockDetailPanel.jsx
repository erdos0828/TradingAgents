(function () {
  const { useEffect, useRef } = React;
  const { useDashboard } = window.__SHAPE__.dashboardContext;
  const { generateSampleCandles, calculateMA } = window.__SHAPE__.dashboardUtils;

  function StockDetailPanel() {
    const { market, activeHolding, stockDetail } = useDashboard();
    const chartContainerRef = useRef(null);
    const chartRef = useRef(null);

    useEffect(() => {
      if (!chartContainerRef.current || !window.LightweightCharts) return;

      const container = chartContainerRef.current;
      container.innerHTML = '';

      const chart = window.LightweightCharts.createChart(container, {
        layout: {
          background: { color: '#111827' },
          textColor: '#94a3b8',
        },
        grid: {
          vertLines: { color: '#2a3a4f' },
          horzLines: { color: '#2a3a4f' },
        },
        crosshair: { mode: window.LightweightCharts.CrosshairMode.Normal },
        rightPriceScale: { borderColor: '#2a3a4f' },
        timeScale: { borderColor: '#2a3a4f' },
      });
      chartRef.current = chart;

      const candlestickSeries = chart.addCandlestickSeries({
        upColor: '#ef4444',
        downColor: '#10b981',
        borderUpColor: '#ef4444',
        borderDownColor: '#10b981',
        wickUpColor: '#ef4444',
        wickDownColor: '#10b981',
      });

      const data = generateSampleCandles(market);
      candlestickSeries.setData(data);

      const colors = { ma5: '#f59e0b', ma10: '#3b82f6', ma20: '#8b5cf6', ma60: '#06b6d4' };
      Object.keys(colors).forEach((key) => {
        const series = chart.addLineSeries({
          color: colors[key],
          lineWidth: 1,
          title: key.toUpperCase(),
        });
        series.setData(calculateMA(data, parseInt(key.slice(2))));
      });

      chart.timeScale().fitContent();

      const handleResize = () => {
        if (chartRef.current) {
          chartRef.current.applyOptions({ width: container.clientWidth });
        }
      };
      window.addEventListener('resize', handleResize);

      return () => {
        window.removeEventListener('resize', handleResize);
        if (chartRef.current) {
          chartRef.current.remove();
          chartRef.current = null;
        }
      };
    }, [market, activeHolding.code]);

    const indicators = [
      { name: 'MA5', color: '#f59e0b' },
      { name: 'MA10', color: '#3b82f6' },
      { name: 'MA20', color: '#8b5cf6' },
      { name: 'MA60', color: '#06b6d4' },
    ];

    return (
      <section className="card">
        <div className="card-title">
          个股速览与决策舱
          <span className="subtitle">技术分析</span>
        </div>
        <div className="stock-header">
          <div>
            <div className="stock-info">
              <span className="stock-name">{activeHolding.name}</span>
              <span className="stock-code">{stockDetail.code}</span>
            </div>
            <div style={{ marginTop: '4px' }}>
              <span className="stock-price">{activeHolding.price}</span>
              <span
                className="stock-price-change"
                style={{ color: activeHolding.up ? 'var(--red)' : 'var(--green)' }}
              >
                {stockDetail.change}
              </span>
            </div>
          </div>
          <div className="stock-actions">
            <button className="btn btn-buy">买入</button>
            <button className="btn btn-sell">卖出</button>
          </div>
        </div>
        <div className="chart-container" ref={chartContainerRef}></div>
        <div className="indicators-bar">
          {indicators.map((i) => (
            <div className="indicator-tag" key={i.name}>
              <span className="dot" style={{ background: i.color }}></span>
              <span>{i.name}</span>
            </div>
          ))}
        </div>
      </section>
    );
  }

  window.__SHAPE__.dashboardStockDetailPanel = StockDetailPanel;
})();
