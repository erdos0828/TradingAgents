#!/usr/bin/env python3
"""Simple report browser for TradingAgents reports.

Serves a small web UI that lets you pick a ticker and date, then browse the
report sections (complete report, analysts, research, trading, risk, portfolio)
in tabs.

Usage:
    python scripts/report_server.py [--port 8080] [--reports-dir ./reports]

No external dependencies are required (uses only the Python standard library).
"""

import argparse
import json
import mimetypes
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

REPORTS_DIR = Path("reports")
DEFAULT_PORT = 8080

INDEX_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TradingAgents 报告浏览</title>
    <style>
        :root {
            --bg: #0f172a;
            --panel: #1e293b;
            --panel-hover: #334155;
            --text: #e2e8f0;
            --muted: #94a3b8;
            --accent: #38bdf8;
            --border: #334155;
            --tab-active: #38bdf8;
            --tab-inactive: #64748b;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            height: 100vh;
            display: flex;
            overflow: hidden;
        }
        .sidebar {
            width: 280px;
            background: var(--panel);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            padding: 20px;
        }
        .sidebar h1 {
            font-size: 18px;
            margin: 0 0 20px;
            color: var(--accent);
        }
        .field {
            margin-bottom: 16px;
        }
        .field label {
            display: block;
            font-size: 12px;
            color: var(--muted);
            margin-bottom: 6px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .field select {
            width: 100%;
            padding: 10px 12px;
            border-radius: 8px;
            border: 1px solid var(--border);
            background: var(--bg);
            color: var(--text);
            font-size: 14px;
            outline: none;
        }
        .field select option {
            background: var(--bg);
            color: var(--text);
        }
        .field select:focus {
            border-color: var(--accent);
        }
        .date-list {
            flex: 1;
            overflow-y: auto;
            margin-top: 8px;
        }
        .date-item {
            padding: 10px 12px;
            border-radius: 8px;
            cursor: pointer;
            margin-bottom: 6px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border: 1px solid transparent;
        }
        .date-item:hover {
            background: var(--panel-hover);
        }
        .date-item.active {
            background: var(--panel-hover);
            border-color: var(--accent);
        }
        .date-item .date-label {
            font-size: 14px;
        }
        .date-item .badge {
            font-size: 11px;
            color: var(--muted);
            background: var(--bg);
            padding: 2px 8px;
            border-radius: 12px;
        }
        .main {
            flex: 1;
            display: flex;
            flex-direction: column;
            min-width: 0;
        }
        .toolbar {
            padding: 16px 24px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--panel);
        }
        .toolbar h2 {
            margin: 0;
            font-size: 16px;
            font-weight: 500;
        }
        .toolbar .meta {
            font-size: 13px;
            color: var(--muted);
        }
        .tabs {
            display: flex;
            gap: 4px;
            padding: 12px 24px 0;
            border-bottom: 1px solid var(--border);
            background: var(--panel);
            overflow-x: auto;
        }
        .tab {
            padding: 10px 16px;
            border: none;
            background: transparent;
            color: var(--tab-inactive);
            font-size: 14px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            white-space: nowrap;
        }
        .tab:hover {
            color: var(--text);
        }
        .tab.active {
            color: var(--tab-active);
            border-bottom-color: var(--tab-active);
        }
        .content {
            flex: 1;
            overflow-y: auto;
            padding: 24px;
        }
        .report-frame {
            max-width: 900px;
            margin: 0 auto;
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 32px;
            line-height: 1.7;
        }
        .report-frame h1,
        .report-frame h2,
        .report-frame h3,
        .report-frame h4 {
            margin-top: 1.5em;
            margin-bottom: 0.6em;
        }
        .report-frame h1 { font-size: 28px; border-bottom: 1px solid var(--border); padding-bottom: 0.3em; }
        .report-frame h2 { font-size: 22px; color: var(--accent); }
        .report-frame h3 { font-size: 18px; }
        .report-frame p { margin: 0.8em 0; }
        .report-frame pre {
            background: var(--bg);
            padding: 16px;
            border-radius: 8px;
            overflow-x: auto;
        }
        .report-frame code {
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 0.9em;
        }
        .report-frame ul, .report-frame ol {
            padding-left: 1.5em;
        }
        .report-frame blockquote {
            border-left: 4px solid var(--accent);
            margin: 1em 0;
            padding-left: 16px;
            color: var(--muted);
        }
        .report-frame table {
            border-collapse: collapse;
            width: 100%;
            margin: 1em 0;
        }
        .report-frame th, .report-frame td {
            border: 1px solid var(--border);
            padding: 8px 12px;
            text-align: left;
        }
        .report-frame th {
            background: var(--bg);
        }
        .empty {
            color: var(--muted);
            text-align: center;
            padding: 60px 20px;
        }
        .loading {
            color: var(--muted);
            text-align: center;
            padding: 40px;
        }

        /* Technical indicators tab (TradingView style) */
        .ta-container {
            max-width: 1100px;
            margin: 0 auto;
        }
        .ta-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid var(--border);
        }
        .ta-header h2 {
            margin: 0;
            font-size: 20px;
        }
        .ta-header .ta-date {
            font-size: 13px;
            color: var(--muted);
        }
        .ta-summary-row {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            margin-bottom: 32px;
        }
        .ta-summary-card {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
        }
        .ta-summary-card .card-title {
            font-size: 14px;
            color: var(--muted);
            margin-bottom: 12px;
        }
        .ta-gauge {
            width: 140px;
            height: 70px;
            margin: 0 auto 12px;
            position: relative;
            overflow: hidden;
        }
        .ta-gauge::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 140px;
            height: 140px;
            border-radius: 50%;
            background: conic-gradient(
                from 180deg,
                #ef4444 0deg 36deg,
                #f87171 36deg 72deg,
                #94a3b8 72deg 108deg,
                #60a5fa 108deg 144deg,
                #3b82f6 144deg 180deg
            );
            mask: radial-gradient(circle at 50% 100%, transparent 55px, black 56px);
            -webkit-mask: radial-gradient(circle at 50% 100%, transparent 55px, black 56px);
        }
        .ta-gauge-needle {
            position: absolute;
            bottom: 0;
            left: 50%;
            width: 2px;
            height: 60px;
            background: #1f2937;
            transform-origin: bottom center;
            transform: translateX(-50%) rotate(-90deg);
            border-radius: 2px;
            z-index: 2;
        }
        .ta-gauge-center {
            position: absolute;
            bottom: -6px;
            left: 50%;
            width: 12px;
            height: 12px;
            background: #1f2937;
            border-radius: 50%;
            transform: translateX(-50%);
            z-index: 3;
        }
        .ta-gauge-labels {
            display: flex;
            justify-content: space-between;
            font-size: 10px;
            color: var(--muted);
            margin-top: 4px;
            padding: 0 8px;
        }
        .ta-verdict {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 12px;
        }
        .ta-verdict.strong-sell { color: #ef4444; }
        .ta-verdict.sell { color: #f87171; }
        .ta-verdict.neutral { color: #94a3b8; }
        .ta-verdict.buy { color: #60a5fa; }
        .ta-verdict.strong-buy { color: #3b82f6; }
        .ta-votes {
            display: flex;
            justify-content: center;
            gap: 16px;
            font-size: 13px;
        }
        .ta-votes span {
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .ta-votes .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        .ta-votes .sell { background: #f87171; }
        .ta-votes .neutral { background: #94a3b8; }
        .ta-votes .buy { background: #60a5fa; }
        .ta-section {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            margin-bottom: 20px;
            overflow: hidden;
        }
        .ta-section-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            cursor: pointer;
            font-weight: 500;
            border-bottom: 1px solid transparent;
        }
        .ta-section-header:hover {
            background: var(--panel-hover);
        }
        .ta-section.open .ta-section-header {
            border-bottom-color: var(--border);
        }
        .ta-section-body {
            display: none;
            padding: 16px 20px;
        }
        .ta-section.open .ta-section-body {
            display: block;
        }
        .ta-section-toggle {
            color: var(--muted);
            font-size: 12px;
        }
        .ta-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }
        .ta-table th, .ta-table td {
            padding: 10px 12px;
            text-align: left;
            border-bottom: 1px solid var(--border);
        }
        .ta-table th {
            color: var(--muted);
            font-weight: 500;
        }
        .ta-table td:last-child, .ta-table th:last-child {
            text-align: right;
        }
        .ta-signal {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 500;
        }
        .ta-signal.strong-sell { background: rgba(239, 68, 68, 0.15); color: #ef4444; }
        .ta-signal.sell { background: rgba(248, 113, 113, 0.15); color: #f87171; }
        .ta-signal.neutral { background: rgba(148, 163, 184, 0.15); color: #94a3b8; }
        .ta-signal.buy { background: rgba(96, 165, 250, 0.15); color: #60a5fa; }
        .ta-signal.strong-buy { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }
        .ta-pivot-grid {
            display: grid;
            grid-template-columns: 80px repeat(5, 1fr);
            gap: 1px;
            background: var(--border);
            border-radius: 8px;
            overflow: hidden;
            font-size: 13px;
        }
        .ta-pivot-grid > div {
            background: var(--panel);
            padding: 10px 8px;
            text-align: center;
        }
        .ta-pivot-grid > div.header {
            background: var(--bg);
            color: var(--muted);
            font-weight: 500;
        }
        .ta-pivot-grid > div.row-label {
            background: var(--bg);
            color: var(--muted);
            font-weight: 500;
        }
        .ta-empty {
            color: var(--muted);
            text-align: center;
            padding: 60px 20px;
        }
        .ta-error {
            color: #f87171;
            text-align: center;
            padding: 40px 20px;
        }
        @media (max-width: 768px) {
            .ta-summary-row {
                grid-template-columns: 1fr;
            }
            .ta-pivot-grid {
                grid-template-columns: 60px repeat(5, 1fr);
                font-size: 11px;
            }
        }
    </style>
</head>
<body>
    <aside class="sidebar">
        <h1>TradingAgents 报告</h1>
        <div class="field">
            <label>股票代码</label>
            <select id="tickerSelect">
                <option value="">选择 ticker...</option>
            </select>
        </div>
        <div class="field">
            <label>报告日期</label>
            <div class="date-list" id="dateList">
                <div class="empty">请选择 ticker</div>
            </div>
        </div>
    </aside>

    <main class="main">
        <div class="toolbar">
            <h2 id="reportTitle">选择一个报告</h2>
            <span class="meta" id="reportMeta"></span>
        </div>
        <div class="tabs" id="tabs"></div>
        <div class="content" id="content">
            <div class="empty">从左侧选择 ticker 和日期以浏览报告</div>
        </div>
    </main>

    <script>
        const $ = id => document.getElementById(id);

        const TAB_ORDER = [
            { key: 'complete_report.md', label: '核心报告' },
            { key: '1_analysts', label: '分析师' },
            { key: '2_research', label: '研究团队' },
            { key: '3_trading', label: '交易团队' },
            { key: '4_risk', label: '风险管理' },
            { key: '5_portfolio', label: '投资组合' },
        ];

        let reportsData = {};
        let currentTicker = '';
        let currentDate = '';
        let currentFiles = [];

        async function init() {
            try {
                const res = await fetch('/api/reports');
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                reportsData = await res.json();
                console.log('Loaded reports:', reportsData);
                populateTickers();
                applyHashSelection();
            } catch (e) {
                console.error('init failed:', e);
                const msg = `加载报告列表失败: ${e.message}`;
                $('content').innerHTML = `<div class="empty">${msg}</div>`;
                $('dateList').innerHTML = `<div class="empty" style="color:#f87171">${msg}</div>`;
            }
        }

        function applyHashSelection() {
            const hash = window.location.hash.slice(1);
            if (!hash) return;
            const params = new URLSearchParams(hash);
            const ticker = params.get('ticker');
            let date = params.get('date');
            if (!ticker || !date) return;
            if (!reportsData.tickers[ticker]) return;

            const select = $('tickerSelect');
            select.value = ticker;
            currentTicker = ticker;
            renderDates();

            const dateItems = Array.from(document.querySelectorAll('.date-item'));
            let matched = dateItems.find(item => {
                const label = item.querySelector('.date-label')?.textContent || '';
                return label === date;
            });
            if (!matched) {
                matched = dateItems.find(item => {
                    const label = item.querySelector('.date-label')?.textContent || '';
                    return label.startsWith(date);
                });
            }
            if (matched) {
                const label = matched.querySelector('.date-label').textContent;
                selectDate(label, matched);
            } else {
                clearReport();
            }
        }

        function populateTickers() {
            const select = $('tickerSelect');
            select.innerHTML = '<option value="">选择 ticker...</option>';
            Object.keys(reportsData.tickers).sort().forEach(ticker => {
                const opt = document.createElement('option');
                opt.value = ticker;
                opt.textContent = ticker;
                select.appendChild(opt);
            });
            select.addEventListener('change', onTickerChange);
        }

        function onTickerChange(e) {
            currentTicker = e.target.value;
            currentDate = '';
            renderDates();
            clearReport();
        }

        function renderDates() {
            const list = $('dateList');
            list.innerHTML = '';
            if (!currentTicker) {
                list.innerHTML = '<div class="empty">请选择 ticker</div>';
                return;
            }
            const dates = reportsData.tickers[currentTicker] || [];
            if (dates.length === 0) {
                list.innerHTML = '<div class="empty">暂无报告</div>';
                return;
            }
            dates.forEach(date => {
                const item = document.createElement('div');
                item.className = 'date-item';
                item.innerHTML = `<span class="date-label">${date}</span><span class="badge">浏览</span>`;
                item.addEventListener('click', () => selectDate(date, item));
                list.appendChild(item);
            });
        }

        async function selectDate(date, itemEl) {
            currentDate = date;
            document.querySelectorAll('.date-item').forEach(el => el.classList.remove('active'));
            itemEl.classList.add('active');

            $('reportTitle').textContent = `${currentTicker} · ${currentDate}`;
            $('reportMeta').textContent = '加载中...';
            $('content').innerHTML = '<div class="loading">加载文件列表...</div>';

            try {
                const res = await fetch(`/api/report/${currentTicker}/${currentDate}/__files__`);
                currentFiles = await res.json();
                renderTabs();
                if (currentFiles.length > 0) {
                    loadFile(currentFiles[0].path);
                } else {
                    $('content').innerHTML = '<div class="empty">该日期下没有报告文件</div>';
                }
            } catch (e) {
                $('content').innerHTML = `<div class="empty">加载失败: ${e.message}</div>`;
            }
        }

        function getTabInfo(path) {
            if (path === 'complete_report.md') return { label: '核心报告', order: 0 };
            for (let i = 0; i < TAB_ORDER.length; i++) {
                if (path.startsWith(TAB_ORDER[i].key)) {
                    return { label: TAB_ORDER[i].label, order: i };
                }
            }
            return { label: path, order: 99 };
        }

        function renderTabs() {
            const tabs = $('tabs');
            tabs.innerHTML = '';

            currentFiles.forEach(file => {
                const info = getTabInfo(file.path);
                file.order = info.order;
                file.label = info.label;
            });
            currentFiles.sort((a, b) => a.order - b.order);

            currentFiles.forEach((file, idx) => {
                const btn = document.createElement('button');
                btn.className = 'tab' + (idx === 0 ? ' active' : '');
                btn.textContent = file.label;
                btn.dataset.path = file.path;
                btn.addEventListener('click', () => {
                    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                    btn.classList.add('active');
                    loadFile(file.path);
                });
                tabs.appendChild(btn);
            });

            // Technical indicators tab (data from SQLite cache)
            const taBtn = document.createElement('button');
            taBtn.className = 'tab';
            taBtn.textContent = '技术指标';
            taBtn.dataset.ta = 'true';
            taBtn.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                taBtn.classList.add('active');
                loadTechnicalIndicators();
            });
            tabs.appendChild(taBtn);
        }

        async function loadFile(path) {
            $('content').innerHTML = '<div class="loading">加载内容...</div>';
            try {
                const res = await fetch(`/api/report/${currentTicker}/${currentDate}/${path}`);
                const text = await res.text();
                $('reportMeta').textContent = path;
                $('content').innerHTML = `<article class="report-frame">${renderMarkdown(text)}</article>`;
            } catch (e) {
                $('content').innerHTML = `<div class="empty">加载失败: ${e.message}</div>`;
            }
        }

        async function loadTechnicalIndicators() {
            $('content').innerHTML = '<div class="loading">加载技术指标...</div>';
            $('reportMeta').textContent = 'TradingView 技术指标';

            const reportDate = currentDate.slice(0, 10);
            try {
                const res = await fetch(`/api/ta/${currentTicker}/${reportDate}`);
                if (!res.ok) {
                    const err = await res.json().catch(() => ({}));
                    $('content').innerHTML = `<div class="ta-error">暂无技术指标数据：${err.error || res.statusText}</div>`;
                    return;
                }
                const payload = await res.json();
                $('content').innerHTML = renderTechnicalIndicators(payload);
                attachTASectionToggles();
            } catch (e) {
                $('content').innerHTML = `<div class="ta-error">加载失败: ${e.message}</div>`;
            }
        }

        function taClassFromSignal(signal) {
            const s = (signal || '').toUpperCase();
            if (s === 'STRONG_BUY') return 'strong-buy';
            if (s === 'BUY') return 'buy';
            if (s === 'STRONG_SELL') return 'strong-sell';
            if (s === 'SELL') return 'sell';
            return 'neutral';
        }

        function taClassFromRec(rec) {
            const r = (rec || '').toUpperCase();
            if (r === 'STRONG_BUY') return 'strong-buy';
            if (r === 'BUY') return 'buy';
            if (r === 'STRONG_SELL') return 'strong-sell';
            if (r === 'SELL') return 'sell';
            return 'neutral';
        }

        function taLabelFromRec(rec) {
            const map = {
                'STRONG_BUY': '强烈买入',
                'BUY': '买入',
                'NEUTRAL': '中立',
                'SELL': '卖出',
                'STRONG_SELL': '强烈卖出'
            };
            return map[(rec || '').toUpperCase()] || rec || '中立';
        }

        function taGaugeAngle(rec) {
            const r = (rec || '').toUpperCase();
            const angles = {
                'STRONG_SELL': -72,
                'SELL': -36,
                'NEUTRAL': 0,
                'BUY': 36,
                'STRONG_BUY': 72
            };
            return angles[r] || 0;
        }

        function taGaugeCard(title, rec, buy, sell, neutral) {
            const cls = taClassFromRec(rec);
            const angle = taGaugeAngle(rec);
            return `
                <div class="ta-summary-card">
                    <div class="card-title">${title}</div>
                    <div class="ta-gauge">
                        <div class="ta-gauge-needle" style="transform: translateX(-50%) rotate(${angle}deg)"></div>
                        <div class="ta-gauge-center"></div>
                    </div>
                    <div class="ta-gauge-labels">
                        <span>强卖</span>
                        <span>卖</span>
                        <span>中</span>
                        <span>买</span>
                        <span>强买</span>
                    </div>
                    <div class="ta-verdict ${cls}">${taLabelFromRec(rec)}</div>
                    <div class="ta-votes">
                        <span><span class="dot sell"></span>卖出 ${sell}</span>
                        <span><span class="dot neutral"></span>中立 ${neutral}</span>
                        <span><span class="dot buy"></span>买入 ${buy}</span>
                    </div>
                </div>
            `;
        }

        function taSignalBadge(signal) {
            const cls = taClassFromSignal(signal);
            const labels = {
                'strong-buy': '强烈买入',
                'buy': '买入',
                'neutral': '中立',
                'sell': '卖出',
                'strong-sell': '强烈卖出'
            };
            return `<span class="ta-signal ${cls}">${labels[cls] || signal || '中立'}</span>`;
        }

        function taIndicatorTable(items) {
            if (!items || items.length === 0) return '<div class="ta-empty">无数据</div>';
            const rows = items.map(([name, value, signal]) => `
                <tr>
                    <td>${name}</td>
                    <td>${value !== null && value !== undefined ? value : '—'}</td>
                    <td>${taSignalBadge(signal)}</td>
                </tr>
            `).join('');
            return `<table class="ta-table"><thead><tr><th>名称</th><th>值</th><th>操作</th></tr></thead><tbody>${rows}</tbody></table>`;
        }

        function taPivotTable(indicators) {
            const types = ['Classic', 'Fibonacci', 'Camarilla', 'Woodie', 'Demark'];
            const labels = ['S3', 'S2', 'S1', 'Middle', 'R1', 'R2', 'R3'];
            const displayLabels = ['S3', 'S2', 'S1', 'P', 'R1', 'R2', 'R3'];
            const typeNames = { 'Classic': '经典', 'Fibonacci': '斐波那契', 'Camarilla': '卡玛利亚', 'Woodie': '伍迪', 'Demark': 'DM' };

            let html = '<div class="ta-pivot-grid">';
            html += '<div class="header">枢轴点</div>';
            types.forEach(t => html += `<div class="header">${typeNames[t] || t}</div>`);

            labels.forEach((label, idx) => {
                html += `<div class="row-label">${displayLabels[idx]}</div>`;
                types.forEach(type => {
                    let key;
                    if (type === 'Demark') {
                        if (label === 'Middle') key = `Pivot.M.Demark.Middle`;
                        else if (label === 'S1') key = `Pivot.M.Demark.S1`;
                        else if (label === 'R1') key = `Pivot.M.Demark.R1`;
                        else key = null;
                    } else {
                        key = `Pivot.M.${type}.${label}`;
                    }
                    const val = key && indicators ? indicators[key] : null;
                    html += `<div>${val !== null && val !== undefined ? Number(val).toFixed(2) : '—'}</div>`;
                });
            });
            html += '</div>';
            return html;
        }

        function renderTechnicalIndicators(payload) {
            const data = payload.data || {};
            const indicators = data.indicators || {};
            const oscillators = data.oscillators || {};
            const movingAverages = data.moving_averages || {};
            const dateText = payload.fallback
                ? `报告日期 ${currentDate.slice(0, 10)} 无缓存，显示最近可用日期 ${payload.date}`
                : `数据日期 ${payload.date}`;

            function countSignals(map) {
                let buy = 0, sell = 0, neutral = 0;
                Object.values(map).forEach(s => {
                    const u = (s || '').toUpperCase();
                    if (u === 'BUY' || u === 'STRONG_BUY') buy++;
                    else if (u === 'SELL' || u === 'STRONG_SELL') sell++;
                    else neutral++;
                });
                return { buy, sell, neutral };
            }

            function recFromCounts({ buy, sell, neutral }) {
                if (sell > buy && sell > neutral) return 'SELL';
                if (buy > sell && buy > neutral) return 'BUY';
                return 'NEUTRAL';
            }

            const oscCounts = countSignals(oscillators);
            const maCounts = countSignals(movingAverages);

            const oscItems = Object.entries(oscillators).map(([name, signal]) => {
                const keyMap = {
                    'RSI': 'RSI', 'STOCH.K': 'Stoch.K', 'CCI': 'CCI20', 'ADX': 'ADX',
                    'AO': 'AO', 'Mom': 'Mom', 'MACD': 'MACD.macd', 'Stoch.RSI': 'Stoch.RSI.K',
                    'W%R': 'W.R', 'BBP': 'BBPower', 'UO': 'UO'
                };
                const value = indicators[keyMap[name] || name];
                return [name, value !== undefined ? Number(value).toFixed(2) : null, signal];
            });

            const maItems = Object.entries(movingAverages).map(([name, signal]) => {
                const value = indicators[name];
                return [name, value !== undefined ? Number(value).toFixed(2) : null, signal];
            });

            return `
                <div class="ta-container">
                    <div class="ta-header">
                        <h2>${currentTicker} 技术指标</h2>
                        <span class="ta-date">${dateText}</span>
                    </div>
                    <div class="ta-summary-row">
                        ${taGaugeCard('震荡指标', recFromCounts(oscCounts), oscCounts.buy, oscCounts.sell, oscCounts.neutral)}
                        ${taGaugeCard('总结', data.recommendation, data.buy_votes || 0, data.sell_votes || 0, data.neutral_votes || 0)}
                        ${taGaugeCard('移动平均线', recFromCounts(maCounts), maCounts.buy, maCounts.sell, maCounts.neutral)}
                    </div>
                    <div class="ta-section open">
                        <div class="ta-section-header">
                            <span>震荡指标</span>
                            <span class="ta-section-toggle">收起</span>
                        </div>
                        <div class="ta-section-body">
                            ${taIndicatorTable(oscItems)}
                        </div>
                    </div>
                    <div class="ta-section open">
                        <div class="ta-section-header">
                            <span>移动平均线</span>
                            <span class="ta-section-toggle">收起</span>
                        </div>
                        <div class="ta-section-body">
                            ${taIndicatorTable(maItems)}
                        </div>
                    </div>
                    <div class="ta-section open">
                        <div class="ta-section-header">
                            <span>枢轴点</span>
                            <span class="ta-section-toggle">收起</span>
                        </div>
                        <div class="ta-section-body">
                            ${taPivotTable(indicators)}
                        </div>
                    </div>
                </div>
            `;
        }

        function attachTASectionToggles() {
            document.querySelectorAll('.ta-section-header').forEach(header => {
                header.addEventListener('click', () => {
                    const section = header.closest('.ta-section');
                    section.classList.toggle('open');
                    const toggle = header.querySelector('.ta-section-toggle');
                    if (toggle) toggle.textContent = section.classList.contains('open') ? '收起' : '展开';
                });
            });
        }

        function clearReport() {
            $('reportTitle').textContent = '选择一个报告';
            $('reportMeta').textContent = '';
            $('tabs').innerHTML = '';
            $('content').innerHTML = '<div class="empty">从左侧选择 ticker 和日期以浏览报告</div>';
        }

        function renderMarkdown(md) {
            // A tiny Markdown renderer sufficient for TradingAgents reports.
            let html = md
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;');

            // code blocks
            html = html.replace(/```([\\s\\S]*?)```/g, (_, code) => `<pre><code>${code.replace(/^\\n|\\n$/g, '')}</code></pre>`);
            // inline code
            html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
            // headers
            html = html.replace(/^###### (.*)$/gm, '<h6>$1</h6>');
            html = html.replace(/^##### (.*)$/gm, '<h5>$1</h5>');
            html = html.replace(/^#### (.*)$/gm, '<h4>$1</h4>');
            html = html.replace(/^### (.*)$/gm, '<h3>$1</h3>');
            html = html.replace(/^## (.*)$/gm, '<h2>$1</h2>');
            html = html.replace(/^# (.*)$/gm, '<h1>$1</h1>');
            // bold / italic
            html = html.replace(/\\*\\*([^*]+)\\*\\*/g, '<strong>$1</strong>');
            html = html.replace(/\\*([^*]+)\\*/g, '<em>$1</em>');
            // blockquote
            html = html.replace(/^> (.*)$/gm, '<blockquote>$1</blockquote>');
            // unordered lists
            html = html.replace(/^\\s*[-*+] (.*)$/gm, '<li>$1</li>');
            // ordered lists
            html = html.replace(/^\\s*\\d+\\. (.*)$/gm, '<li>$1</li>');
            // wrap consecutive li in ul
            html = html.replace(/(<li>.*<\\/li>\\n?)+/g, match => `<ul>${match}</ul>`);
            // tables (simple pipe tables)
            html = html.replace(/((?:^|\\n)[^\\n|]*\\|[^\\n]*)+/g, block => {
                if (!block.includes('|')) return block;
                const rows = block.trim().split('\\n').filter(r => r.trim());
                if (rows.length < 2) return block;
                let tableHtml = '<table>';
                rows.forEach((row, idx) => {
                    if (row.replace(/[\\|\\-:\\s]/g, '') === '') return;
                    const cells = row.split('|').map(c => c.trim()).filter(c => c !== '');
                    const tag = idx === 0 ? 'th' : 'td';
                    tableHtml += '<tr>' + cells.map(c => `<${tag}>${c}</${tag}>`).join('') + '</tr>';
                });
                tableHtml += '</table>';
                return tableHtml;
            });
            // paragraphs
            html = html.split('\\n\\n').map(block => {
                block = block.trim();
                if (!block) return '';
                if (/^<(h\\d|pre|ul|blockquote|table)/.test(block)) return block;
                return `<p>${block.replace(/\\n/g, '<br>')}</p>`;
            }).join('\\n');

            return html;
        }

        init();
    </script>
</body>
</html>
"""


def scan_reports(reports_dir: Path) -> dict:
    """Scan reports_dir and return {ticker: [date_time, ...]} sorted descending."""
    tickers: dict[str, list[str]] = {}
    if not reports_dir.exists():
        return {"tickers": tickers}

    for ticker_dir in sorted(reports_dir.iterdir()):
        if not ticker_dir.is_dir():
            continue
        entries = []
        for entry_dir in ticker_dir.iterdir():
            if not entry_dir.is_dir():
                continue
            # Accept either {YYYY-MM-DD}_{HHMMSS} or legacy {YYYY-MM-DD}.
            name = entry_dir.name
            try:
                if len(name) == 10:
                    datetime.strptime(name, "%Y-%m-%d")
                else:
                    datetime.strptime(name, "%Y-%m-%d_%H%M%S")
                entries.append(name)
            except ValueError:
                continue
        if entries:
            tickers[ticker_dir.name] = sorted(entries, reverse=True)

    return {"tickers": tickers}


def list_report_files(reports_dir: Path, ticker: str, date_time: str) -> list[dict]:
    """Return all readable report files under reports/{ticker}/{date_time}/."""
    base = reports_dir / ticker / date_time
    if not base.exists():
        return []

    files = []
    for path in sorted(base.rglob("*")):
        if path.is_file() and path.suffix == ".md":
            rel = path.relative_to(base).as_posix()
            files.append({"path": rel, "name": path.name})
    return files


class ReportHandler(BaseHTTPRequestHandler):
    reports_dir: Path = REPORTS_DIR

    def log_message(self, format, *args):
        # Suppress default request logging for cleaner output.
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text: str, content_type: str = "text/plain; charset=utf-8", status=200):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)

        if path == "/" or path == "/index.html":
            self._send_text(INDEX_HTML, "text/html; charset=utf-8")
            return

        if path == "/api/reports":
            self._send_json(scan_reports(self.reports_dir))
            return

        if path.startswith("/api/report/"):
            rest = path[len("/api/report/"):]
            parts = rest.split("/", 2)
            if len(parts) >= 2:
                ticker, date_time = parts[0], parts[1]
                file_path = parts[2] if len(parts) == 3 else ""

                if file_path == "__files__":
                    self._send_json(list_report_files(self.reports_dir, ticker, date_time))
                    return

                target = self.reports_dir / ticker / date_time / file_path
                try:
                    target.resolve().relative_to(self.reports_dir.resolve())
                except ValueError:
                    self._send_text("Forbidden", status=403)
                    return

                if target.exists() and target.is_file():
                    content = target.read_text(encoding="utf-8")
                    self._send_text(content, "text/markdown; charset=utf-8")
                    return
                else:
                    self._send_text("Not found", status=404)
                    return

        self._send_text("Not found", status=404)


def main() -> int:
    parser = argparse.ArgumentParser(description="TradingAgents report browser")
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=REPORTS_DIR,
        help=f"Directory containing reports (default: {REPORTS_DIR}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Server port (default: {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Server host (default: 127.0.0.1).",
    )
    args = parser.parse_args()

    ReportHandler.reports_dir = args.reports_dir.resolve()

    server = HTTPServer((args.host, args.port), ReportHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"Report browser running at {url}")
    print(f"Reports directory: {ReportHandler.reports_dir}")
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
