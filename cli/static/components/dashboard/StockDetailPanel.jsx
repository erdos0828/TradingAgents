(function () {
  const { useEffect, useRef } = React;
  const { useDashboard } = window.__SHAPE__.dashboardContext;

  function StockDetailPanel() {
    const { market, activeHolding, stockDetail, stockData } = useDashboard();
    const chartContainerRef = useRef(null);
    const widgetRef = useRef(null);
    // Cost price line entity, removed and re-created on every symbol switch.
    const costLineIdRef = useRef(null);
    // Latest stock payload for the stale closures inside TV widget events.
    const stockDataRef = useRef(null);

    // (Re)create the dashed cost line from the latest stock data. Stale
    // payloads for another symbol are skipped via the symbol check.
    // NOTE: onChartReady() is callback-style in the library — it does NOT
    // return a Promise.
    const drawCostLine = () => {
      const widget = widgetRef.current;
      const data = stockDataRef.current;
      if (!widget) return;
      widget.onChartReady(() => {
        // onChartReady fires synchronously once ready, so an exception here
        // would bubble into the caller and abort the sibling drawTradeMarkers.
        try {
          const chart = widget.activeChart();
          if (costLineIdRef.current != null) {
            try {
              chart.removeEntity(costLineIdRef.current);
            } catch (e) {
              /* entity already gone */
            }
            costLineIdRef.current = null;
          }
          if (!data || !data.candles || !data.candles.length || !(data.costPrice > 0)) return;
          if (String(chart.symbol()).toUpperCase() !== String(data.ticker).toUpperCase()) return;
          const lastTime = Math.floor(
            new Date(data.candles[data.candles.length - 1].time + 'T00:00:00Z').getTime() / 1000
          );
          chart
            .createShape(
              { time: lastTime, price: data.costPrice },
              {
                shape: 'horizontal_line',
                lock: true,
                disableSelection: true,
                disableSave: true,
                disableUndo: true,
                showInObjectsTree: false,
                overrides: {
                  linecolor: '#d97706',
                  linewidth: 2,
                  linestyle: 2,
                  text: '成本 ' + data.costPrice,
                  showLabel: true,
                },
              }
            )
            .then((id) => {
              costLineIdRef.current = id;
            })
            .catch(() => {
              /* shape rejected, e.g. mid symbol switch */
            });
        } catch (e) {
          console.warn('drawCostLine failed:', e);
        }
      });
    };

    // Create the TradingView widget once. Indicators, panes, drawing tools
    // and the crosshair data window all come from the library itself.
    useEffect(() => {
      const container = chartContainerRef.current;
      if (!container || !window.TradingView || !window.Datafeeds) return undefined;

      const widget = new window.TradingView.widget({
        container,
        datafeed: new window.Datafeeds.UDFCompatibleDatafeed('/tv', 60000),
        symbol: activeHolding.ticker || activeHolding.code || '600006.SS',
        interval: 'D',
        library_path: '/tv_lib/charting_library/',
        locale: 'zh',
        timezone: 'Asia/Shanghai',
        theme: 'dark',
        autosize: true,
        // Chinese market convention: red = up, green = down.
        overrides: {
          'mainSeriesProperties.candleStyle.upColor': '#ef4444',
          'mainSeriesProperties.candleStyle.downColor': '#10b981',
          'mainSeriesProperties.candleStyle.borderUpColor': '#ef4444',
          'mainSeriesProperties.candleStyle.borderDownColor': '#10b981',
          'mainSeriesProperties.candleStyle.wickUpColor': '#ef4444',
          'mainSeriesProperties.candleStyle.wickDownColor': '#10b981',
        },
        disabled_features: [
          'go_to_date',
          'header_symbol_search',
          'header_saveload',
          'header_compare',
          'timeframes_toolbar',
        ],
        enabled_features: ['data_window', 'data_window_show_all_sources'],
        allow_symbol_change: false,
      });
      widgetRef.current = widget;

      // Drop the old cost line whenever the symbol changes so it never
      // carries over to the next ticker's price scale. Buy/sell marks come
      // from the UDF datafeed (/tv/marks), no manual redraw needed.
      // The library persists the viewport (zoom/pan) in localStorage, so a
      // stale view can survive reloads and hide the latest bars — reset the
      // time scale back to the default "latest bars" view on load and on
      // every symbol switch.
      widget.onChartReady(() => {
        try {
          widget.activeChart().executeActionById('timeScaleReset');
        } catch (e) {
          /* action unavailable in this build */
        }
        widget.activeChart().onSymbolChanged().subscribe(null, () => {
          drawCostLine();
          try {
            widget.activeChart().executeActionById('timeScaleReset');
          } catch (e) {
            /* action unavailable in this build */
          }
        });
      });

      return () => {
        try {
          widget.remove();
        } catch (e) {
          /* widget not ready */
        }
        widgetRef.current = null;
        costLineIdRef.current = null;
        container.innerHTML = '';
      };
    }, []);

    // Follow the selected holding.
    useEffect(() => {
      const symbol = activeHolding.ticker || activeHolding.code;
      if (!symbol) return;
      const widget = widgetRef.current;
      if (!widget) return;
      widget.onChartReady(() => {
        widget.setSymbol(symbol, 'D', () => {
          // The viewport reset on symbol change is handled by the
          // onSymbolChanged subscription in the widget effect.
        });
      });
    }, [activeHolding.ticker, activeHolding.code]);

    // Redraw the cost line whenever fresh data arrives. Buy/sell marks are
    // delivered by the UDF datafeed, not drawn here.
    useEffect(() => {
      stockDataRef.current = stockData;
      drawCostLine();
    }, [stockData]);

    // Holding metrics strip (like the classic board): value / qty, price /
    // cost, daily pnl and position pnl.
    const currency = market === 'a-share' ? '¥' : '$';
    const fmtNum = (v) => (v === null || v === undefined || isNaN(v)
      ? '—'
      : Number(v).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
    const fmtPnl = (v) => (v === null || v === undefined || isNaN(v)
      ? '—'
      : (v > 0 ? '+' : '') + fmtNum(v));
    const pnlClass = (v) => (v === null || v === undefined || isNaN(v) || Number(v) === 0
      ? ''
      : Number(v) > 0 ? 'profit' : 'loss');

    // Today's executed trades, shown in the metrics strip above the chart
    // (price/qty live there instead of cluttering the balloons on chart).
    const dayTrades = (stockData && stockData.tradesByDate && stockData.priceDate
      ? stockData.tradesByDate[stockData.priceDate]
      : []) || [];

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
          </div>
        </div>
        <div className="holding-metrics">
          <div className="metric-block">
            <div className="metric-label">市值 / 数量</div>
            <div className="metric-value">
              {activeHolding.marketValue != null && !isNaN(activeHolding.marketValue)
                ? currency + fmtNum(activeHolding.marketValue)
                : '—'}
            </div>
            <div className="metric-sub">
              {activeHolding.quantity != null
                ? Number(activeHolding.quantity).toLocaleString() + ' 股'
                : '—'}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-label">现价 / 成本</div>
            <div className="metric-value">{stockDetail.price}</div>
            <div className="metric-sub">
              {activeHolding.costPrice
                ? '成本 ' + Number(activeHolding.costPrice).toFixed(2)
                : '—'}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-label">当日盈亏</div>
            <div className={'metric-value ' + pnlClass(activeHolding.dailyPnl)}>
              {fmtPnl(activeHolding.dailyPnl)}
            </div>
            <div className={'metric-sub ' + pnlClass(activeHolding.dailyPnl)}>
              {activeHolding.dailyPnlPercent || activeHolding.change || '—'}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-label">持仓盈亏</div>
            <div className={'metric-value ' + pnlClass(activeHolding.positionPnl)}>
              {fmtPnl(activeHolding.positionPnl)}
            </div>
            <div className={'metric-sub ' + pnlClass(activeHolding.positionPnl)}>
              {activeHolding.positionPnlPercent || '—'}
            </div>
          </div>
          <div className="metric-block">
            <div className="metric-label">当日交易</div>
            <div className="metric-value trade-lines">
              {dayTrades.length
                ? dayTrades.map((t, i) => (
                    <span key={i} className={t.side === 'buy' ? 'profit' : 'loss'}>
                      {t.side === 'buy' ? 'B' : 'S'} {Number(t.qty)} @ {t.avgPrice}
                    </span>
                  ))
                : '—'}
            </div>
            <div className="metric-sub">{stockData ? stockData.priceDate : '—'}</div>
          </div>
        </div>
        <div className="tv-chart-wrap">
          <div className="tv-chart-container" ref={chartContainerRef}></div>
        </div>
      </section>
    );
  }

  window.__SHAPE__.dashboardStockDetailPanel = StockDetailPanel;
})();
