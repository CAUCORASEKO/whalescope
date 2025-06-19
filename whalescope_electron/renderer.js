console.log('[Renderer] renderer.js loaded');

document.addEventListener('DOMContentLoaded', () => {
    console.log('[Renderer] DOM content loaded');
    // Verify existence of HTML elements
    const elements = [
        'bitcoin-status', 'blackrock-status', 'lido-status',
        'bitcoin-loading', 'blackrock-loading', 'lido-loading',
        'priceTrendChart', 'feesChart', 'refreshBtn', 'blackrock-refreshBtn', 'lido-refreshBtn',
        'blackrock-totalBalance', 'btcBalanceChart', 'ethBalanceChart', 'lido-ethStakedChart',
        'blackrock-totalBalanceTable', 'lido-marketStatsTableBody', 'lido-yieldsTableBody',
        'lido-analyticsTableBody', 'lido-queuesTableBody',
        'exportCsvBtn', 'blackrock-exportBtn', 'lido-exportBtn', // Added Bitcoin CSV button
        'exportPdfBtn', 'blackrock-exportPdfBtn', 'lido-exportPdfBtn' // Added PDF buttons
    ];
    elements.forEach(id => {
        console.log(`[Renderer] ${id} exists: ${!!document.getElementById(id)}`);
    });

    // Initialize dates
    const today = new Date();
    const endDate = today.toISOString().split('T')[0];
    const startDate = new Date(today - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    console.log(`[Renderer] Initial date range: start=${startDate}, end=${endDate}`);

    ['startDate', 'endDate', 'blackrock-startDate', 'blackrock-endDate', 'lido-startDate', 'lido-endDate'].forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.value = id.includes('start') ? startDate : endDate;
            console.log(`[Renderer] Initialized ${id} with value: ${input.value}`);
        } else {
            console.error(`[Renderer] Input ${id} not found`);
        }
    });

    // Load initial data for bitcoin
    loadSectionData('bitcoin', startDate, endDate);

    // Handle section change
    document.addEventListener('sectionChange', (event) => {
        console.log(`[Renderer] Section change event received:`, event);
        const section = event.detail?.section;
        console.log(`[Renderer] Parsed section: ${section}`);
        if (section) {
            const startDateInput = document.getElementById(`${section}-startDate`)?.value || startDate;
            const endDateInput = document.getElementById(`${section}-endDate`)?.value || endDate;
            console.log(`[Renderer] Loading ${section} with start=${startDateInput}, end=${endDateInput}`);
            loadSectionData(section, startDateInput, endDateInput);
        } else {
            console.error(`[Renderer] Invalid section in sectionChange event:`, event.detail);
        }
    });

    // Bitcoin refresh button
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            console.log('[Renderer] Bitcoin refresh button clicked');
            const startDateInput = document.getElementById('startDate')?.value;
            const endDateInput = document.getElementById('endDate')?.value;
            if (startDateInput && endDateInput && validateDates(startDateInput, endDateInput)) {
                console.log(`[Renderer] Refreshing bitcoin data with start=${startDateInput}, end=${endDateInput}`);
                loadSectionData('bitcoin', startDateInput, endDateInput);
            } else {
                console.error('[Renderer] Invalid date range for bitcoin refresh');
                const status = document.getElementById('bitcoin-status');
                if (status) status.innerHTML = 'Error: Select valid dates (not future and start ≤ end)';
            }
        });
    } else {
        console.error('[Renderer] refreshBtn not found');
    }

    // Bitcoin CSV export button
    const bitcoinCsvBtn = document.getElementById('exportCsvBtn');
    if (bitcoinCsvBtn) {
        bitcoinCsvBtn.addEventListener('click', () => {
            console.log('[Renderer] Bitcoin CSV export button clicked');
            exportBitcoinToCSV();
        });
    } else {
        console.error('[Renderer] exportCsvBtn not found');
    }

    // Bitcoin PDF export button
    const bitcoinPdfBtn = document.getElementById('exportPdfBtn');
    if (bitcoinPdfBtn) {
        bitcoinPdfBtn.addEventListener('click', () => {
            console.log('[Renderer] Bitcoin PDF export button clicked');
            exportBitcoinToPDF();
        });
    } else {
        console.error('[Renderer] exportPdfBtn not found');
    }

    // BlackRock refresh button
    const blackrockRefreshBtn = document.getElementById('blackrock-refreshBtn');
    if (blackrockRefreshBtn) {
        blackrockRefreshBtn.addEventListener('click', () => {
            console.log('[Renderer] BlackRock refresh button clicked');
            const startDateInput = document.getElementById('blackrock-startDate')?.value;
            const endDateInput = document.getElementById('blackrock-endDate')?.value;
            if (startDateInput && endDateInput && validateDates(startDateInput, endDateInput)) {
                console.log(`[Renderer] Refreshing blackrock data with start=${startDateInput}, end=${endDateInput}`);
                loadSectionData('blackrock', startDateInput, endDateInput);
            } else {
                console.error('[Renderer] Invalid date range for blackrock refresh');
                const status = document.getElementById('blackrock-status');
                if (status) status.innerHTML = 'Error: Select valid dates (not future and start ≤ end)';
            }
        });
    } else {
        console.error('[Renderer] blackrock-refreshBtn not found');
    }

    // BlackRock CSV export button
    const blackrockExportBtn = document.getElementById('blackrock-exportBtn');
    if (blackrockExportBtn) {
        blackrockExportBtn.addEventListener('click', () => {
            console.log('[Renderer] BlackRock CSV export button clicked');
            exportBlackRockToCSV();
        });
    } else {
        console.error('[Renderer] blackrock-exportBtn not found');
    }

    // BlackRock PDF export button
    const blackrockPdfBtn = document.getElementById('blackrock-exportPdfBtn');
    if (blackrockPdfBtn) {
        blackrockPdfBtn.addEventListener('click', () => {
            console.log('[Renderer] BlackRock PDF export button clicked');
            exportBlackRockToPDF();
        });
    } else {
        console.error('[Renderer] blackrock-exportPdfBtn not found');
    }

    // Lido refresh button
    const lidoRefreshBtn = document.getElementById('lido-refreshBtn');
    if (lidoRefreshBtn) {
        lidoRefreshBtn.addEventListener('click', () => {
            console.log('[Renderer] Lido refresh button clicked');
            const startDateInput = document.getElementById('lido-startDate')?.value;
            const endDateInput = document.getElementById('lido-endDate')?.value;
            if (startDateInput && endDateInput && validateDates(startDateInput, endDateInput)) {
                console.log(`[Renderer] Refreshing lido data with start=${startDateInput}, end=${endDateInput}`);
                loadSectionData('lido', startDateInput, endDateInput);
            } else {
                console.error('[Renderer] Invalid date range for lido refresh');
                const status = document.getElementById('lido-status');
                if (status) status.innerHTML = 'Error: Select valid dates (not future and start ≤ end)';
            }
        });
    } else {
        console.error('[Renderer] lido-refreshBtn not found');
    }

    // Lido CSV export button
    const lidoExportBtn = document.getElementById('lido-exportBtn');
    if (lidoExportBtn) {
        lidoExportBtn.addEventListener('click', () => {
            console.log('[Renderer] Lido CSV export button clicked');
            exportLidoToCSV();
        });
    } else {
        console.error('[Renderer] lido-exportBtn not found');
    }

    // Lido PDF export button
    const lidoPdfBtn = document.getElementById('lido-exportPdfBtn');
    if (lidoPdfBtn) {
        lidoPdfBtn.addEventListener('click', () => {
            console.log('[Renderer] Lido PDF export button clicked');
            exportLidoToPDF();
        });
    } else {
        console.error('[Renderer] lido-exportPdfBtn not found');
    }

    // Handle chart resizing
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            const plotlyCharts = ['priceTrendChart', 'feesChart', 'btcBalanceChart', 'ethBalanceChart', 'lido-ethStakedChart'];
            plotlyCharts.forEach(id => {
                const chart = document.getElementById(id);
                if (chart && chart.data) {
                    console.log(`[Renderer] Resizing ${id}`);
                    Plotly.Plots.resize(chart);
                }
            });
        }, 200);
    });
});

// Existing validateDates function (unchanged)
function validateDates(startDate, endDate) {
    const today = new Date().setHours(0, 0, 0, 0);
    const start = new Date(startDate).setHours(0, 0, 0, 0);
    const end = new Date(endDate).setHours(0, 0, 0, 0);
    if (start > today || end > today) {
        console.error('[Renderer] Dates cannot be in the future');
        return false;
    }
    if (start > end) {
        console.error('[Renderer] Start date must be before or equal to end date');
        return false;
    }
    return true;
}

// New Bitcoin CSV export function
function exportBitcoinToCSV() {
    const data = window.bitcoinData;
    if (!data || !data.price_history) {
        console.error('[Renderer] No Bitcoin data to export');
        document.getElementById('bitcoin-status').innerHTML = 'Error: No data available for export';
        return;
    }

    const csvRows = [];
    csvRows.push('Date,Open,High,Low,Close,Volume,Market Cap');
    data.price_history.dates.forEach((date, index) => {
        csvRows.push([
            date,
            data.price_history.open[index].toFixed(2),
            data.price_history.high[index].toFixed(2),
            data.price_history.low[index].toFixed(2),
            data.price_history.close[index].toFixed(2),
            (data.markets?.volume_24h || 0).toFixed(2), // Adjust based on actual data
            (data.markets?.market_cap || 0).toFixed(2)
        ].join(','));
    });

    const csvString = csvRows.join('\n');
    const blob = new Blob([csvString], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `bitcoin_data_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    console.log('[Renderer] Bitcoin data exported to CSV');
    document.getElementById('bitcoin-status').innerHTML = 'CSV exported successfully';
}

// New Bitcoin PDF export function
function exportBitcoinToPDF() {
    const data = window.bitcoinData;
    if (!data || !data.price_history) {
        console.error('[Renderer] No Bitcoin data to export');
        document.getElementById('bitcoin-status').innerHTML = 'Error: No data available for export';
        return;
    }

    try {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        doc.text('Bitcoin Data', 10, 10);
        let y = 20;
        doc.text('Date | Open | High | Low | Close | Volume | Market Cap', 10, y);
        y += 10;
        data.price_history.dates.forEach((date, index) => {
            doc.text(
                `${date} | ${data.price_history.open[index].toFixed(2)} | ${data.price_history.high[index].toFixed(2)} | ` +
                `${data.price_history.low[index].toFixed(2)} | ${data.price_history.close[index].toFixed(2)} | ` +
                `${(data.markets?.volume_24h || 0).toFixed(2)} | ${(data.markets?.market_cap || 0).toFixed(2)}`,
                10, y
            );
            y += 10;
        });
        doc.save(`bitcoin_data_${new Date().toISOString().split('T')[0]}.pdf`);
        console.log('[Renderer] Bitcoin data exported to PDF');
        document.getElementById('bitcoin-status').innerHTML = 'PDF exported successfully';
    } catch (error) {
        console.error('[Renderer] Error exporting Bitcoin PDF:', error);
        document.getElementById('bitcoin-status').innerHTML = `Error exporting PDF: ${error.message}`;
    }
}

// Existing BlackRock CSV export function (unchanged)
function exportBlackRockToCSV() {
    const data = window.blackrockData;
    if (!data) {
        console.error('[Renderer] No BlackRock data to export');
        document.getElementById('blackrock-status').innerHTML = 'Error: No data available for export';
        return;
    }

    const csvRows = [];
    csvRows.push('Week End,Total Balance (USD),BTC Balance (USD),BTC Balance (BTC),ETH Balance (USD),ETH Balance (ETH)');
    data.historical_total_balance.forEach((total, index) => {
        const btc = data.historical_balances.BTC[index] || {};
        const eth = data.historical_balances.ETH[index] || {};
        csvRows.push([
            total.week_end,
            total.total_balance_usd.toFixed(2),
            (btc.balance_usd || 0).toFixed(2),
            (btc.balance || 0).toFixed(8),
            (eth.balance_usd || 0).toFixed(2),
            (eth.balance || 0).toFixed(8)
        ].join(','));
    });

    const csvString = csvRows.join('\n');
    const blob = new Blob([csvString], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `blackrock_balances_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    console.log('[Renderer] BlackRock data exported to CSV');
    document.getElementById('blackrock-status').innerHTML = 'CSV exported successfully';
}

// New BlackRock PDF export function
function exportBlackRockToPDF() {
    const data = window.blackrockData;
    if (!data || !data.historical_total_balance) {
        console.error('[Renderer] No BlackRock data to export');
        document.getElementById('blackrock-status').innerHTML = 'Error: No data available for export';
        return;
    }

    try {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        doc.text('BlackRock Data', 10, 10);
        let y = 20;
        doc.text('Week End | Total Balance (USD) | BTC Balance (USD) | BTC Balance (BTC) | ETH Balance (USD) | ETH Balance (ETH)', 10, y);
        y += 10;
        data.historical_total_balance.forEach((total, index) => {
            const btc = data.historical_balances.BTC[index] || {};
            const eth = data.historical_balances.ETH[index] || {};
            doc.text(
                `${total.week_end} | ${total.total_balance_usd.toFixed(2)} | ${(btc.balance_usd || 0).toFixed(2)} | ` +
                `${(btc.balance || 0).toFixed(8)} | ${(eth.balance_usd || 0).toFixed(2)} | ${(eth.balance || 0).toFixed(8)}`,
                10, y
            );
            y += 10;
        });
        doc.save(`blackrock_data_${new Date().toISOString().split('T')[0]}.pdf`);
        console.log('[Renderer] BlackRock data exported to PDF');
        document.getElementById('blackrock-status').innerHTML = 'PDF exported successfully';
    } catch (error) {
        console.error('[Renderer] Error exporting BlackRock PDF:', error);
        document.getElementById('blackrock-status').innerHTML = `Error exporting PDF: ${error.message}`;
    }
}

// Existing Lido CSV export function (unchanged)
function exportLidoToCSV() {
    const data = window.lidoData;
    if (!data) {
        console.error('[Renderer] No Lido data to export');
        document.getElementById('lido-status').innerHTML = 'Error: No data available for export';
        return;
    }

    const csvRows = [];
    csvRows.push('Week End,Total ETH Deposited,ETH Staked,ETH Unstaked,Staking Rewards');
    data.charts.forEach(chart => {
        csvRows.push([
            chart.week_end,
            chart.total_eth_deposited.toFixed(2),
            chart.eth_staked.toFixed(2),
            chart.eth_unstaked.toFixed(2),
            chart.staking_rewards.toFixed(2)
        ].join(','));
    });

    const csvString = csvRows.join('\n');
    const blob = new Blob([csvString], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `lido_data_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
    console.log('[Renderer] Lido data exported to CSV');
    document.getElementById('lido-status').innerHTML = 'CSV exported successfully';
}

// New Lido PDF export function
function exportLidoToPDF() {
    const data = window.lidoData;
    if (!data || !data.charts) {
        console.error('[Renderer] No Lido data to export');
        document.getElementById('lido-status').innerHTML = 'Error: No data available for export';
        return;
    }

    try {
        const { jsPDF } = window.jspdf;
        const doc = new jsPDF();
        doc.text('Lido Staking Data', 10, 10);
        let y = 20;
        doc.text('Week End | Total ETH Deposited | ETH Staked | ETH Unstaked | Staking Rewards', 10, y);
        y += 10;
        data.charts.forEach(chart => {
            doc.text(
                `${chart.week_end} | ${chart.total_eth_deposited.toFixed(2)} | ${chart.eth_staked.toFixed(2)} | ` +
                `${chart.eth_unstaked.toFixed(2)} | ${chart.staking_rewards.toFixed(2)}`,
                10, y
            );
            y += 10;
        });
        doc.save(`lido_data_${new Date().toISOString().split('T')[0]}.pdf`);
        console.log('[Renderer] Lido data exported to PDF');
        document.getElementById('lido-status').innerHTML = 'PDF exported successfully';
    } catch (error) {
        console.error('[Renderer] Error exporting Lido PDF:', error);
        document.getElementById('lido-status').innerHTML = `Error exporting PDF: ${error.message}`;
    }
}

// Existing loadSectionData function (unchanged)
async function loadSectionData(section, startDate, endDate) {
    console.log(`[Renderer] loadSectionData called for ${section} with start=${startDate}, end=${endDate}`);
    const status = document.getElementById(`${section}-status`);
    const loading = document.getElementById(`${section}-loading`);

    if (loading) loading.style.display = 'block';
    if (status) status.innerHTML = 'Loading...';

    try {
        if (!window.electronAPI?.loadData) {
            throw new Error('electronAPI.loadData is not defined');
        }
        console.log('[Renderer] Sending IPC request for', section);
        const data = await window.electronAPI.loadData({ section, startDate, endDate });
        console.log(`[Renderer] Data received for ${section}:`, JSON.stringify(data, null, 2));

        if (data.error) {
            console.error(`[Renderer] Error: ${data.error}`);
            if (status) status.innerHTML = `Error: ${data.error}`;
            if (loading) loading.style.display = 'none';
            return;
        }

        if (status) status.innerHTML = 'Data loaded successfully';
        if (loading) loading.style.display = 'none';

        if (section === 'bitcoin') {
            window.bitcoinData = data; // Store data globally
            const table = document.getElementById('marketStatsTableBody');
            const lastUpdated = document.getElementById('lastUpdated');
            const performanceTable = document.getElementById('performanceTableBody');
            const topFlowsTable = document.getElementById('topFlowsTableBody');
            const flowsTable = document.getElementById('flowsTableBody');
            const priceTrendChart = document.getElementById('priceTrendChart');
            const feesChart = document.getElementById('feesChart');
            const analysis = document.getElementById('marketAnalysis');
            const conclusion = document.getElementById('marketConclusion');

            console.log(`[Renderer] Bitcoin DOM elements:`, {
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

            if (table) table.innerHTML = '<tr><td colspan="2">Fetching data...</td></tr>';
            if (performanceTable) performanceTable.innerHTML = '<tr><td colspan="2">Fetching data...</td></tr>';
            if (topFlowsTable) topFlowsTable.innerHTML = '<tr><td colspan="4">Fetching data...</td></tr>';
            if (flowsTable) flowsTable.innerHTML = '<tr><td colspan="2">Fetching data...</td></tr>';
            if (analysis) analysis.textContent = 'Fetching analysis...';
            if (conclusion) conclusion.textContent = 'Fetching conclusion...';

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

            if (lastUpdated && data.markets?.last_updated) {
                console.log('[Renderer] Updating last update');
                lastUpdated.textContent = new Date(data.markets.last_updated).toLocaleString();
            }

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
            } else if (priceTrendChart) {
                console.log('[Renderer] Price trend chart not updated: missing price_history data');
                Plotly.purge(priceTrendChart);
                document.getElementById('priceTrendError').innerHTML = 'No price history data available';
            }

            if (feesChart && data.fees?.dates && data.fees?.values) {
                console.log('[Renderer] Updating fees chart');
                Plotly.purge(feesChart);
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
                    console.log('[Renderer] No fee data in selected range');
                    document.getElementById('feesError').innerHTML = 'No fee data available for selected range';
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
                        text: 'Transaction Fees',
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
            } else if (feesChart) {
                console.log('[Renderer] Fees chart not updated: missing fee data');
                Plotly.purge(feesChart);
                document.getElementById('feesError').innerHTML = 'No fee data available';
            }

            if (analysis && data.analysis) {
                console.log(`[Renderer] Updating analysis: ${data.analysis}`);
                analysis.textContent = data.analysis;
            } else {
                console.log('[Renderer] No analysis data available');
                if (analysis) analysis.textContent = 'No analysis available';
            }

            if (conclusion && data.conclusion) {
                console.log(`[Renderer] Updating conclusion: ${data.conclusion}`);
                conclusion.textContent = data.conclusion;
            } else {
                console.log('[Renderer] No conclusion data available');
                if (conclusion) conclusion.textContent = 'No conclusion available';
            }
        } else if (section === 'blackrock') {
            const totalBalance = document.getElementById('blackrock-totalBalance');
            const totalBalanceTable = document.getElementById('blackrock-totalBalanceTable');
            const btcBalanceChart = document.getElementById('btcBalanceChart');
            const ethBalanceChart = document.getElementById('ethBalanceChart');
            const totalBalanceError = document.getElementById('blackrock-totalBalanceError');
            const btcBalanceChartError = document.getElementById('btcBalanceChartError');
            const ethBalanceChartError = document.getElementById('ethBalanceChartError');

            console.log(`[Renderer] BlackRock DOM elements:`, {
                totalBalance: !!totalBalance,
                totalBalanceTable: !!totalBalanceTable,
                btcBalanceChart: !!btcBalanceChart,
                ethBalanceChart: !!ethBalanceChart,
                totalBalanceError: !!totalBalanceError,
                btcBalanceChartError: !!btcBalanceChartError,
                ethBalanceChartError: !!ethBalanceChartError
            });

            if (totalBalanceError) totalBalanceError.innerHTML = '';
            if (btcBalanceChartError) btcBalanceChartError.innerHTML = '';
            if (ethBalanceChartError) ethBalanceChartError.innerHTML = '';

            window.blackrockData = data;

            if (totalBalance && data.historical_total_balance?.length > 0) {
                console.log('[Renderer] Updating BlackRock total balance');
                const latestBalance = data.historical_total_balance.slice(-1)[0].total_balance_usd;
                totalBalance.textContent = `$${latestBalance.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
            } else {
                console.log('[Renderer] No total balance data');
                if (totalBalanceError) totalBalanceError.innerHTML = 'No total balance data available';
                if (totalBalance) totalBalance.textContent = 'N/A';
            }

            if (totalBalanceTable && data.historical_total_balance?.length > 0) {
                console.log('[Renderer] Updating total balance table');
                totalBalanceTable.innerHTML = `
                    <table>
                        <tr><th>Week Ending</th><th>Total Balance (USD)</th></tr>
                        ${data.historical_total_balance.map(entry => `
                            <tr>
                                <td>${entry.week_end}</td>
                                <td>$${entry.total_balance_usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                            </tr>
                        `).join('')}
                    </table>
                `;
            }

            if (btcBalanceChart && data.historical_balances?.BTC?.length > 0) {
                console.log('[Renderer] Updating BTC balance chart');
                Plotly.purge(btcBalanceChart);
                const trace = {
                    x: data.historical_balances.BTC.map(item => item.week_end),
                    y: data.historical_balances.BTC.map(item => item.balance_usd),
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: 'BTC Balance (USD)',
                    line: { color: '#0d6efd', width: 2 },
                    marker: { size: 8, color: '#0d6efd', symbol: 'circle' },
                    text: data.historical_balances.BTC.map(item => `$${item.balance_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}`),
                    hovertemplate: '%{text}<br>Date: %{x}<extra></extra>'
                };
                Plotly.newPlot(btcBalanceChart, [trace], {
                    title: {
                        text: 'BlackRock BTC Balance (USD)',
                        font: { family: 'Arial, sans-serif', size: 18, color: '#ffffff' }
                    },
                    xaxis: {
                        title: { text: 'Week Ending', font: { color: '#cccccc' } },
                        tickfont: { color: '#cccccc' },
                        gridcolor: '#333',
                        range: [startDate, endDate]
                    },
                    yaxis: {
                        title: { text: 'Balance (USD)', font: { color: '#cccccc' } },
                        tickfont: { color: '#cccccc' },
                        gridcolor: '#333',
                        tickprefix: '$',
                        tickformat: ',.2f'
                    },
                    plot_bgcolor: '#1e1e1e',
                    paper_bgcolor: '#1e1e1e',
                    margin: { t: 50, b: 50, l: 50, r: 50 },
                    autosize: true
                }, {
                    responsive: true
                });
            } else {
                console.log('[Renderer] No BTC balance data');
                if (btcBalanceChartError) btcBalanceChartError.innerHTML = 'No BTC balance data available';
                if (btcBalanceChart) Plotly.purge(btcBalanceChart);
            }

            if (ethBalanceChart && data.historical_balances?.ETH?.length > 0) {
                console.log('[Renderer] Updating ETH balance chart');
                Plotly.purge(ethBalanceChart);
                const trace = {
                    x: data.historical_balances.ETH.map(item => item.week_end),
                    y: data.historical_balances.ETH.map(item => item.balance_usd),
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: 'ETH Balance (USD)',
                    line: { color: '#28a745', width: 2 },
                    marker: { size: 8, color: '#28a745', symbol: 'circle' },
                    text: data.historical_balances.ETH.map(item => `$${item.balance_usd.toLocaleString('en-US', { minimumFractionDigits: 2 })}`),
                    hovertemplate: '%{text}<br>Date: %{x}<extra></extra>'
                };
                Plotly.newPlot(ethBalanceChart, [trace], {
                    title: {
                        text: 'BlackRock ETH Balance (USD)',
                        font: { family: 'Arial, sans-serif', size: 18, color: '#ffffff' }
                    },
                    xaxis: {
                        title: { text: 'Week Ending', font: { color: '#cccccc' } },
                        tickfont: { color: '#cccccc' },
                        gridcolor: '#333',
                        range: [startDate, endDate]
                    },
                    yaxis: {
                        title: { text: 'Balance (USD)', font: { color: '#cccccc' } },
                        tickfont: { color: '#cccccc' },
                        gridcolor: '#333',
                        tickprefix: '$',
                        tickformat: ',.2f'
                    },
                    plot_bgcolor: '#1e1e1e',
                    paper_bgcolor: '#1e1e1e',
                    margin: { t: 50, b: 50, l: 50, r: 50 },
                    autosize: true
                }, {
                    responsive: true
                });
            } else {
                console.log('[Renderer] No ETH balance data');
                if (ethBalanceChartError) ethBalanceChartError.innerHTML = 'No ETH balance data available';
                if (ethBalanceChart) Plotly.purge(ethBalanceChart);
            }
        } else if (section === 'lido') {
            const marketStatsTable = document.getElementById('lido-marketStatsTableBody');
            const yieldsTable = document.getElementById('lido-yieldsTableBody');
            const analyticsTable = document.getElementById('lido-analyticsTableBody');
            const queuesTable = document.getElementById('lido-queuesTableBody');
            const ethStakedChart = document.getElementById('lido-ethStakedChart');
            const ethStakedChartError = document.getElementById('lido-ethStakedChartError');

            console.log(`[Renderer] Lido DOM elements:`, {
                marketStatsTable: !!marketStatsTable,
                yieldsTable: !!yieldsTable,
                analyticsTable: !!analyticsTable,
                queuesTable: !!queuesTable,
                ethStakedChart: !!ethStakedChart,
                ethStakedChartError: !!ethStakedChartError
            });

            if (ethStakedChartError) ethStakedChartError.innerHTML = '';

            window.lidoData = data;

            if (marketStatsTable && data.markets?.stETH) {
                console.log('[Renderer] Updating Lido market stats table');
                marketStatsTable.innerHTML = '';
                const metrics = [
                    { key: 'total_eth_deposited', label: 'Total ETH Deposited', format: v => `${v.toFixed(2)} ETH` },
                    { key: 'eth_staked', label: 'ETH Staked', format: v => `${v.toFixed(2)} ETH` },
                    { key: 'eth_unstaked', label: 'ETH Unstaked', format: v => `${v.toFixed(2)} ETH` },
                    { key: 'staking_rewards', label: 'Staking Rewards', format: v => `${v.toFixed(2)} ETH` }
                ];
                metrics.forEach(metric => {
                    if (data.markets.stETH[metric.key] !== undefined) {
                        const row = document.createElement('tr');
                        row.innerHTML = `<td>${metric.label}</td><td>${metric.format(data.markets.stETH[metric.key])}</td>`;
                        marketStatsTable.appendChild(row);
                        console.log(`[Renderer] Added row for ${metric.label}`);
                    }
                });
            }

            if (yieldsTable && data.yields) {
                console.log('[Renderer] Updating Lido yields table');
                yieldsTable.innerHTML = '';
                const row = document.createElement('tr');
                row.innerHTML = `<td>Average Rewards</td><td>${data.yields.avg_rewards.toFixed(2)}%</td>`;
                yieldsTable.appendChild(row);
                console.log('[Renderer] Added row for Average Rewards');
            }

            if (analyticsTable && data.analytics) {
                console.log('[Renderer] Updating Lido analytics table');
                analyticsTable.innerHTML = '';
                const row = document.createElement('tr');
                row.innerHTML = `<td>Staking Ratio</td><td>${(data.analytics.staking_ratio * 100).toFixed(2)}%</td>`;
                analyticsTable.appendChild(row);
                console.log('[Renderer] Added row for Staking Ratio');
            }

            if (queuesTable && data.analytics?.queues) {
                console.log('[Renderer] Updating Lido queues table');
                queuesTable.innerHTML = '';
                data.analytics.queues.forEach(queue => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${queue.queue_type.charAt(0).toUpperCase() + queue.queue_type.slice(1)}</td>
                        <td>${queue.eth_amount.toFixed(2)} ETH</td>
                        <td>${(queue.avg_wait_time / (24 * 60 * 60)).toFixed(2)} days</td>
                    `;
                    queuesTable.appendChild(row);
                    console.log(`[Renderer] Added row for ${queue.queue_type} queue`);
                });
            }

            if (ethStakedChart && data.charts?.length > 0) {
                console.log('[Renderer] Updating Lido ETH staked chart');
                Plotly.purge(ethStakedChart);
                const trace = {
                    x: data.charts.map(item => item.week_end),
                    y: data.charts.map(item => item.eth_staked),
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: 'ETH Staked',
                    line: { color: '#28a745', width: 2 },
                    marker: { size: 8, color: '#28a745', symbol: 'circle' },
                    text: data.charts.map(item => `${item.eth_staked.toFixed(2)} ETH`),
                    hovertemplate: '%{text}<br>Date: %{x}<extra></extra>'
                };
                Plotly.newPlot(ethStakedChart, [trace], {
                    title: {
                        text: 'Lido ETH Staked Over Time',
                        font: { family: 'Arial, sans-serif', size: 18, color: '#ffffff' }
                    },
                    xaxis: {
                        title: { text: 'Week Ending', font: { color: '#cccccc' } },
                        tickfont: { color: '#cccccc' },
                        gridcolor: '#333',
                        range: [startDate, endDate]
                    },
                    yaxis: {
                        title: { text: 'ETH Staked', font: { color: '#cccccc' } },
                        tickfont: { color: '#cccccc' },
                        gridcolor: '#333',
                        tickformat: ',.2f'
                    },
                    plot_bgcolor: '#1e1e1e',
                    paper_bgcolor: '#1e1e1e',
                    margin: { t: 50, b: 50, l: 50, r: 50 },
                    autosize: true
                }, {
                    responsive: true
                });
            } else {
                console.log('[Renderer] No ETH staked chart data');
                if (ethStakedChartError) ethStakedChartError.innerHTML = 'No historical ETH staked data available';
                if (ethStakedChart) Plotly.purge(ethStakedChart);
            }
        }
    } catch (err) {
        console.error(`[Renderer] Error: ${err.message}`);
        if (status) status.innerHTML = `Error: ${err.message}`;
        if (loading) loading.style.display = 'none';
    }
}