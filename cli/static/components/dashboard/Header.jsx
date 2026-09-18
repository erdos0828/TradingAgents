(function () {
  const { useState, useEffect, useRef, useMemo } = React;
  const { useDashboard } = window.__SHAPE__.dashboardContext;

  const DOW_HEADERS = ['一', '二', '三', '四', '五', '六', '日'];

  function toISODate(d) {
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    return `${d.getFullYear()}-${mm}-${dd}`;
  }

  function parseISODate(s) {
    const [y, m, d] = s.split('-').map(Number);
    return new Date(y, m - 1, d);
  }

  // Lightweight dark-theme calendar popup: month navigation, Monday-first grid,
  // report-date dots (from availableDates), today ring, future days disabled.
  function DatePicker({ value, onChange, availableDates }) {
    const [open, setOpen] = useState(false);
    const [view, setView] = useState(() => {
      const base = value ? parseISODate(value) : new Date();
      return { year: base.getFullYear(), month: base.getMonth() };
    });
    const rootRef = useRef(null);

    // Close the popup when clicking outside of it.
    useEffect(() => {
      if (!open) return undefined;
      const handleDocClick = (ev) => {
        if (rootRef.current && !rootRef.current.contains(ev.target)) setOpen(false);
      };
      document.addEventListener('mousedown', handleDocClick);
      return () => document.removeEventListener('mousedown', handleDocClick);
    }, [open]);

    const availableSet = useMemo(() => new Set(availableDates || []), [availableDates]);
    const todayStr = toISODate(new Date());

    const leadingBlanks = (new Date(view.year, view.month, 1).getDay() + 6) % 7; // Monday-first
    const daysInMonth = new Date(view.year, view.month + 1, 0).getDate();

    const cells = [];
    for (let i = 0; i < leadingBlanks; i++) cells.push(null);
    for (let d = 1; d <= daysInMonth; d++) cells.push(d);

    const moveMonth = (delta) => {
      setView((v) => {
        const nd = new Date(v.year, v.month + delta, 1);
        return { year: nd.getFullYear(), month: nd.getMonth() };
      });
    };

    const pick = (day) => {
      onChange(toISODate(new Date(view.year, view.month, day)));
      setOpen(false);
    };

    const goToday = () => {
      onChange(todayStr);
      setView({ year: new Date().getFullYear(), month: new Date().getMonth() });
      setOpen(false);
    };

    return (
      <div className="date-picker" ref={rootRef}>
        <button
          type="button"
          className={`date-picker-trigger${open ? ' open' : ''}`}
          onClick={() => setOpen(!open)}
          title="热力图基准日期"
        >
          <svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="1.4">
            <rect x="1.5" y="2.5" width="13" height="12" rx="2" />
            <path d="M1.5 6h13M5 1.5v2M11 1.5v2" />
          </svg>
          <span>{value || '最新日期'}</span>
          <span className="date-picker-caret">▾</span>
        </button>
        {open && (
          <div className="date-picker-panel">
            <div className="date-picker-nav">
              <button type="button" onClick={() => moveMonth(-1)} title="上个月">‹</button>
              <span className="date-picker-month">{view.year}年 {view.month + 1}月</span>
              <button type="button" onClick={() => moveMonth(1)} title="下个月">›</button>
            </div>
            <div className="date-picker-grid date-picker-dow">
              {DOW_HEADERS.map((w) => <span key={w}>{w}</span>)}
            </div>
            <div className="date-picker-grid">
              {cells.map((day, i) => {
                if (day === null) return <span key={`blank-${i}`} className="date-picker-cell blank" />;
                const iso = toISODate(new Date(view.year, view.month, day));
                const isFuture = iso > todayStr;
                const cls = [
                  'date-picker-cell',
                  iso === todayStr ? 'today' : '',
                  iso === value ? 'selected' : '',
                  isFuture ? 'future' : '',
                ].filter(Boolean).join(' ');
                return (
                  <button key={iso} type="button" className={cls} disabled={isFuture} onClick={() => pick(day)}>
                    {day}
                    {availableSet.has(iso) && <i className="date-picker-dot" />}
                  </button>
                );
              })}
            </div>
            <div className="date-picker-footer">
              <span className="date-picker-hint">● 有报告</span>
              <button type="button" className="date-picker-today" onClick={goToday}>今天</button>
            </div>
          </div>
        )}
      </div>
    );
  }

  function Header() {
    const { market, setMarket, indices, matrixDate, setMatrixDate, matrixDates } = useDashboard();

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
        <div className="header-controls">
          <DatePicker value={matrixDate} onChange={setMatrixDate} availableDates={matrixDates} />
          <div className="market-toggle">
            <button className={market === 'a-share' ? 'active' : ''} onClick={() => setMarket('a-share')}>
              A股市场
            </button>
            <button className={market === 'us' ? 'active' : ''} onClick={() => setMarket('us')}>
              美股市场
            </button>
          </div>
        </div>
      </header>
    );
  }

  window.__SHAPE__.dashboardHeader = Header;
})();
