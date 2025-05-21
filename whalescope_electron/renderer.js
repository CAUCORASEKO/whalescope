console.log('[Renderer] renderer.js loaded');

document.addEventListener('DOMContentLoaded', () => {
    console.log('[Renderer] DOM content loaded');
    console.log(`[Renderer] marketStatsTableBody exists: ${!!document.getElementById('marketStatsTableBody')}`);
    console.log(`[Renderer] bitcoin-status exists: ${!!document.getElementById('bitcoin-status')}`);
    console.log(`[Renderer] marketAnalysis exists: ${!!document.getElementById('marketAnalysis')}`);
    console.log(`[Renderer] marketConclusion exists: ${!!document.getElementById('marketConclusion')}`);
    console.log(`[Renderer] priceTrendChart exists: ${!!document.getElementById('priceTrendChart')}`);
    console.log(`[Renderer] feesChart exists: ${!!document.getElementById('feesChart')}`);
    console.log(`[Renderer] refreshBtn exists: ${!!document.getElementById('refreshBtn')}`);

    // Set initial date range
    const endDate = new Date().toISOString().split('T')[0];
    const startDate = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]; // Default to 30 days
    console.log(`[Renderer] Initial date range: start=${startDate}, end=${endDate}`);
    document.getElementById('startDate').value = startDate;
    document.getElementById('endDate').value = endDate;

    loadSectionData('bitcoin', startDate, endDate);

    // Handle section change
    document.addEventListener('sectionChange', (event) => {
        const section = event.detail?.section;
        console.log(`[Renderer] Section change event: ${section}`);
        if (section) {
            const startDateInput = document.getElementById('startDate')?.value || startDate;
            const endDateInput = document.getElementById('endDate')?.value || endDate;
            loadSectionData(section, startDateInput, endDateInput);
        }
    });

    // Handle refresh button click
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            console.log('[Renderer] Refresh button clicked');
            const startDateInput = document.getElementById('startDate')?.value;
            const endDateInput = document.getElementById('endDate')?.value;
            if (startDateInput && endDateInput) {
                console.log(`[Renderer] Refreshing data with start=${startDateInput}, end=${endDateInput}`);
                loadSectionData('bitcoin', startDateInput, endDateInput);
            } else {
                console.log('[Renderer] Invalid date range for refresh');
                const status = document.getElementById('bitcoin-status');
                if (status) status.innerHTML = 'Error: Please select valid start and end dates';
            }
        });
    } else {
        console.log('[Renderer] refreshBtn not found');
    }

    // Handle window resize to update charts
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            const priceTrendChart = document.getElementById('priceTrendChart');
            const feesChart = document.getElementById('feesChart');
            if (priceTrendChart && priceTrendChart.data) {
                console.log('[Renderer] Resizing price trend chart');
                Plotly.Plots.resize(priceTrendChart);
            }
            if (feesChart && feesChart.data) {
                console.log('[Renderer] Resizing fees chart');
                Plotly.Plots.resize(feesChart);
            }
        }, 200); // Debounce de 200ms
    });
});

async function loadSectionData(section, startDate, endDate) {
    console.log(`[Renderer] loadSectionData called for ${section} with start=${startDate}, end=${endDate}`);
    const status = document.getElementById('bitcoin-status');
    const table = document.getElementById('marketStatsTableBody');
    const lastUpdated = document.getElementById('lastUpdated');
    const performanceTable = document.getElementById('performanceTableBody');
    const topFlowsTable = document.getElementById('topFlowsTableBody');
    const flowsTable = document.getElementById('flowsTableBody');
    const priceTrendChart = document.getElementById('priceTrendChart');
    const feesChart = document.getElementById('feesChart');
    const analysis = document.getElementById('marketAnalysis');
    const conclusion = document.getElementById('marketConclusion');

    console.log(`[Renderer] DOM elements:`, {
        status: !!status,
        table: !!table,
        lastUpdated: !!lastUpdated,
        performanceTable: !!performanceTable,
        topFlowsTable: !!topFlowsTable,
        flowsTable: !!flowsTable,
        priceTrendChart: !!priceTrendChart,
        feesChart: !!feesChart,
        analysis: !!analysis,
        conclusion: !!conclusion
    });

    if (status) status.innerHTML = 'Loading...';
    if (table) table.innerHTML = '<tr><td colspan="2">Fetching data...</td></tr>';
    if (performanceTable) performanceTable.innerHTML = '<tr><td colspan="2">Fetching data...</td></tr>';
    if (topFlowsTable) topFlowsTable.innerHTML = '<tr><td colspan="4">Fetching data...</td></tr>';
    if (flowsTable) flowsTable.innerHTML = '<tr><td colspan="2">Fetching data...</td></tr>';
    if (analysis) analysis.textContent = 'Fetching analysis...';
    if (conclusion) conclusion.textContent = 'Fetching conclusion...';

    try {
        if (!window.electronAPI?.loadData) {
            throw new Error('electronAPI.loadData not defined');
        }
        console.log('[Renderer] Sending IPC request');
        const data = await window.electronAPI.loadData({ section, startDate, endDate });
        console.log(`[Renderer] Received data:`, {
            markets: !!data.markets,
            yields: !!data.yields,
            top_flows: !!data.top_flows,
            inflows: !!data.inflows,
            fees: !!data.fees,
            price_history: !!data.price_history,
            analysis: !!data.analysis,
            conclusion: !!data.conclusion
        });

        if (data.error) {
            console.log(`[Renderer] Error: ${data.error}`);
            if (status) status.innerHTML = `Error: ${data.error}`;
            return;
        }

        if (status) status.innerHTML = 'Data loaded successfully';

        // Update market stats table
        if (table && data.markets) {
            console.log('[Renderer] Updating market stats table');
            table.innerHTML = '';
            const metrics = [
                { key: 'price', label: 'Price (USD)', format: v => `$${v.toFixed(2)}` },
                { key: 'percent_change_24h', label: '24h Change (%)', format: v => `${v.toFixed(2)}%` },
                { key: 'market_cap', label: 'Market Cap (USD)', format: v => `$${v.toFixed(2)}` },
                { key: 'volume_24h', label: '24h Volume (USD)', format: v => `$${v.toFixed(2)}` }
            ];
            metrics.forEach(metric => {
                if (data.markets[metric.key] !== undefined) {
                    const row = document.createElement('tr');
                    row.innerHTML = `<td>${metric.label}</td><td>${metric.format(data.markets[metric.key])}</td>`;
                    table.appendChild(row);
                    console.log(`[Renderer] Added row for ${metric.label}`);
                }
            });
        }

        // Update last updated
        if (lastUpdated && data.markets?.last_updated) {
            console.log('[Renderer] Updating lastUpdated');
            lastUpdated.textContent = new Date(data.markets.last_updated).toLocaleString();
        }

        // Update performance metrics
        if (performanceTable && data.yields) {
            console.log('[Renderer] Updating performance table');
            performanceTable.innerHTML = '';
            const periods = [
                { key: 'percent_change_24h', label: '24h' },
                { key: 'percent_change_7d', label: '7d' },
                { key: 'percent_change_30d', label: '30d' }
            ];
            periods.forEach(period => {
                if (data.yields[period.key] !== undefined) {
                    const row = document.createElement('tr');
                    row.innerHTML = `<td>${period.label}</td><td>${data.yields[period.key].toFixed(2)}%</td>`;
                    performanceTable.appendChild(row);
                    console.log(`[Renderer] Added row for ${period.label}`);
                }
            });
        }

        // Update whale activity (top flows)
        if (topFlowsTable && data.top_flows) {
            console.log('[Renderer] Updating top flows table');
            topFlowsTable.innerHTML = '';
            data.top_flows.forEach(flow => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${flow.time}</td>
                    <td>$${flow.input_total_usd.toFixed(2)}</td>
                    <td>$${flow.output_total_usd.toFixed(2)}</td>
                    <td>${flow.is_confirmed ? 'Confirmed' : 'Pending'}</td>
                `;
                topFlowsTable.appendChild(row);
                console.log(`[Renderer] Added row for flow at ${flow.time}`);
            });
        }

        // Update exchange flows
        if (flowsTable && (data.inflows || data.outflows || data.net_flow)) {
            console.log('[Renderer] Updating flows table');
            flowsTable.innerHTML = '';
            const flows = [
                { key: 'inflows', label: 'Inflows (BTC)' },
                { key: 'outflows', label: 'Outflows (BTC)' },
                { key: 'net_flow', label: 'Net Flow (BTC)' }
            ];
            flows.forEach(flow => {
                if (data[flow.key] !== undefined) {
                    const row = document.createElement('tr');
                    row.innerHTML = `<td>${flow.label}</td><td>${data[flow.key].toFixed(2)}</td>`;
                    flowsTable.appendChild(row);
                    console.log(`[Renderer] Added row for ${flow.label}`);
                }
            });
        }

        // Update price trend chart (candlestick)
        if (priceTrendChart && data.price_history) {
            console.log('[Renderer] Updating price trend chart');
            Plotly.purge(priceTrendChart);
            const trace = {
                x: data.price_history.dates,
                open: data.price_history.open,
                high: data.price_history.high,
                low: data.price_history.low,
                close: data.price_history.close,
                type: 'candlestick',
                increasing: { line: { color: '#0d6efd' } },
                decreasing: { line: { color: '#dc3545' } }
            };
            Plotly.newPlot(priceTrendChart, [trace], {
                title: {
                    // text: 'Bitcoin Price Trend', // Simplified title
                    font: { family: 'Arial, sans-serif', size: 18, color: '#ffffff' }
                },
                xaxis: {
                    title: { text: 'Date', font: { color: '#cccccc' } },
                    tickfont: { color: '#cccccc' },
                    gridcolor: '#333',
                    range: [startDate, endDate]
                },
                yaxis: {
                    title: { text: 'Price (USD)', font: { color: '#cccccc' } },
                    tickfont: { color: '#cccccc' },
                    gridcolor: '#333'
                },
                plot_bgcolor: '#1e1e1e',
                paper_bgcolor: '#1e1e1e',
                margin: { t: 50, b: 50, l: 50, r: 50 },
                autosize: true
            }, {
                responsive: true
            });
        } else {
            console.log('[Renderer] Price trend chart not updated: price_history missing');
            if (priceTrendChart) {
                Plotly.purge(priceTrendChart);
                priceTrendChart.innerHTML = 'No price history data available';
            }
        }

        // Update fees chart (line with points)
        if (feesChart && data.fees?.dates && data.fees?.values) {
            console.log('[Renderer] Updating fees chart');
            Plotly.purge(feesChart);
            // Filter fees data by date range
            const start = new Date(startDate).getTime();
            const end = new Date(endDate).getTime();
            const filteredIndices = data.fees.dates
                .map((date, index) => ({ date, index }))
                .filter(({ date }) => {
                    const d = new Date(date).getTime();
                    return d >= start && d <= end;
                })
                .map(({ index }) => index);
            const filteredDates = filteredIndices.map(i => data.fees.dates[i]);
            const filteredValues = filteredIndices.map(i => data.fees.values[i]);

            if (filteredDates.length === 0) {
                console.log('[Renderer] No fees data in selected date range');
                feesChart.innerHTML = 'No fees data available for selected date range';
                return;
            }

            const trace = {
                x: filteredDates,
                y: filteredValues,
                type: 'scatter',
                mode: 'lines+markers',
                name: 'Transaction Fees',
                line: { color: '#0d6efd', width: 2 },
                marker: { size: 8, color: '#0d6efd', symbol: 'circle' }
            };
            Plotly.newPlot(feesChart, [trace], {
                title: {
                    text: 'Transaction Fees', // Simplified title
                    font: { family: 'Arial, sans-serif', size: 18, color: '#ffffff' }
                },
                xaxis: {
                    title: { text: 'Date', font: { color: '#cccccc' } },
                    tickfont: { color: '#cccccc' },
                    gridcolor: '#333',
                    range: [startDate, endDate]
                },
                yaxis: {
                    title: { text: 'Fee (USD)', font: { color: '#cccccc' } },
                    tickfont: { color: '#cccccc' },
                    gridcolor: '#333'
                },
                plot_bgcolor: '#1e1e1e',
                paper_bgcolor: '#1e1e1e',
                margin: { t: 50, b: 50, l: 50, r: 50 },
                autosize: true
            }, {
                responsive: true
            });
        } else {
            console.log('[Renderer] Fees chart not updated: fees data missing');
            if (feesChart) {
                Plotly.purge(feesChart);
                feesChart.innerHTML = 'No fees data available';
            }
        }

        // Update analysis
        if (analysis && data.analysis) {
            console.log(`[Renderer] Updating analysis: ${data.analysis}`);
            analysis.textContent = data.analysis;
        } else {
            console.log('[Renderer] No analysis data available');
            if (analysis) analysis.textContent = 'No analysis available';
        }

        // Update conclusion
        if (conclusion && data.conclusion) {
            console.log(`[Renderer] Updating conclusion: ${data.conclusion}`);
            conclusion.textContent = data.conclusion;
        } else {
            console.log('[Renderer] No conclusion data available');
            if (conclusion) conclusion.textContent = 'No conclusion available';
        }
    } catch (err) {
        console.log(`[Renderer] Error: ${err.message}`);
        if (status) status.innerHTML = `Error: ${err.message}`;
    }
}