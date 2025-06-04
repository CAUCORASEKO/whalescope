console.log('[Renderer] renderer.js cargado');

document.addEventListener('DOMContentLoaded', () => {
    console.log('[Renderer] Contenido DOM cargado');
    // Verificar existencia de elementos HTML
    const elements = [
        'marketStatsTableBody', 'blackrock-balancesTableBody', 'bitcoin-status', 'blackrock-status',
        'bitcoin-loading', 'blackrock-loading', 'marketAnalysis', 'marketConclusion',
        'priceTrendChart', 'feesChart', 'walletsChart', 'refreshBtn', 'blackrock-refreshBtn',
        'blackrock-transactionsChart', 'blackrock-fedCorrelationTableBody', 'transactionsChartError'
    ];
    elements.forEach(id => {
        console.log(`[Renderer] ${id} existe: ${!!document.getElementById(id)}`);
    });

    // Inicializar fechas
    const today = new Date();
    const endDate = today.toISOString().split('T')[0];
    const startDate = new Date(today - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0];
    console.log(`[Renderer] Rango de fechas inicial: inicio=${startDate}, fin=${endDate}`);

    ['startDate', 'endDate', 'blackrock-startDate', 'blackrock-endDate'].forEach(id => {
        const input = document.getElementById(id);
        if (input) {
            input.value = id.includes('start') ? startDate : endDate;
            console.log(`[Renderer] Inicializado ${id} con valor: ${input.value}`);
        } else {
            console.error(`[Renderer] Input ${id} no encontrado`);
        }
    });

    // Cargar datos iniciales para bitcoin
    loadSectionData('bitcoin', startDate, endDate);

    // Manejar cambio de sección
    document.addEventListener('sectionChange', (event) => {
        console.log(`[Renderer] Evento de cambio de sección recibido:`, event);
        const section = event.detail?.section;
        console.log(`[Renderer] Sección parseada: ${section}`);
        if (section) {
            const startDateInput = document.getElementById(`${section}-startDate`)?.value || startDate;
            const endDateInput = document.getElementById(`${section}-endDate`)?.value || endDate;
            console.log(`[Renderer] Cargando ${section} con inicio=${startDateInput}, fin=${endDateInput}`);
            loadSectionData(section, startDateInput, endDateInput);
        } else {
            console.error(`[Renderer] Sección inválida en evento sectionChange:`, event.detail);
        }
    });

    // Botón de refresco para bitcoin
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            console.log('[Renderer] Botón de refresco de Bitcoin clicado');
            const startDateInput = document.getElementById('startDate')?.value;
            const endDateInput = document.getElementById('endDate')?.value;
            if (startDateInput && endDateInput && validateDates(startDateInput, endDateInput)) {
                console.log(`[Renderer] Refrescando datos de bitcoin con inicio=${startDateInput}, fin=${endDateInput}`);
                loadSectionData('bitcoin', startDateInput, endDateInput);
            } else {
                console.error('[Renderer] Rango de fechas inválido para refresco de bitcoin');
                const status = document.getElementById('bitcoin-status');
                if (status) status.innerHTML = 'Error: Selecciona fechas válidas (no futuras y inicio ≤ fin)';
            }
        });
    } else {
        console.error('[Renderer] refreshBtn no encontrado');
    }

    // Botón de refresco para blackrock
    const blackrockRefreshBtn = document.getElementById('blackrock-refreshBtn');
    if (blackrockRefreshBtn) {
        blackrockRefreshBtn.addEventListener('click', () => {
            console.log('[Renderer] Botón de refresco de BlackRock clicado');
            const startDateInput = document.getElementById('blackrock-startDate')?.value;
            const endDateInput = document.getElementById('blackrock-endDate')?.value;
            if (startDateInput && endDateInput && validateDates(startDateInput, endDateInput)) {
                console.log(`[Renderer] Refrescando datos de blackrock con inicio=${startDateInput}, fin=${endDateInput}`);
                loadSectionData('blackrock', startDateInput, endDateInput);
            } else {
                console.error('[Renderer] Rango de fechas inválido para refresco de blackrock');
                const status = document.getElementById('blackrock-status');
                if (status) status.innerHTML = 'Error: Selecciona fechas válidas (no futuras y inicio ≤ fin)';
            }
        });
    } else {
        console.error('[Renderer] blackrock-refreshBtn no encontrado');
    }

    // Manejar redimensionamiento de gráficos
    let resizeTimeout;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimeout);
        resizeTimeout = setTimeout(() => {
            const plotlyCharts = ['priceTrendChart', 'feesChart'];
            plotlyCharts.forEach(id => {
                const chart = document.getElementById(id);
                if (chart && chart.data) {
                    console.log(`[Renderer] Redimensionando ${id}`);
                    Plotly.Plots.resize(chart);
                }
            });
            const chartJsCharts = ['walletsChart', 'blackrock-transactionsChart'];
            chartJsCharts.forEach(id => {
                const chart = document.getElementById(id);
                if (chart && chart.chartInstance) {
                    console.log(`[Renderer] Redimensionando ${id}`);
                    chart.chartInstance.resize();
                }
            });
        }, 200);
    });
});

function validateDates(startDate, endDate) {
    const today = new Date().setHours(0, 0, 0, 0);
    const start = new Date(startDate).setHours(0, 0, 0, 0);
    const end = new Date(endDate).setHours(0, 0, 0, 0);
    if (start > today || end > today) {
        console.error('[Renderer] Las fechas no pueden ser futuras');
        return false;
    }
    if (start > end) {
        console.error('[Renderer] La fecha de inicio debe ser anterior o igual a la fecha de fin');
        return false;
    }
    return true;
}

async function loadSectionData(section, startDate, endDate) {
    console.log(`[Renderer] loadSectionData llamado para ${section} con inicio=${startDate}, fin=${endDate}`);
    const status = document.getElementById(`${section}-status`);
    const loading = document.getElementById(`${section}-loading`);

    if (loading) loading.style.display = 'block';
    if (status) status.innerHTML = 'Cargando...';

    try {
        if (!window.electronAPI?.loadData) {
            throw new Error('electronAPI.loadData no está definido');
        }
        console.log('[Renderer] Enviando solicitud IPC para', section);
        const data = await window.electronAPI.loadData({ section, startDate, endDate });
        console.log(`[Renderer] Datos recibidos para ${section}:`, JSON.stringify(data, null, 2));

        if (data.error) {
            console.error(`[Renderer] Error: ${data.error}`);
            if (status) status.innerHTML = `Error: ${data.error}`;
            if (loading) loading.style.display = 'none';
            return;
        }

        if (status) status.innerHTML = 'Datos cargados correctamente';
        if (loading) loading.style.display = 'none';

        if (section === 'bitcoin') {
            const table = document.getElementById('marketStatsTableBody');
            const lastUpdated = document.getElementById('lastUpdated');
            const performanceTable = document.getElementById('performanceTableBody');
            const topFlowsTable = document.getElementById('topFlowsTableBody');
            const flowsTable = document.getElementById('flowsTableBody');
            const priceTrendChart = document.getElementById('priceTrendChart');
            const feesChart = document.getElementById('feesChart');
            const analysis = document.getElementById('marketAnalysis');
            const conclusion = document.getElementById('marketConclusion');

            console.log(`[Renderer] Elementos DOM de Bitcoin:`, {
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

            if (table) table.innerHTML = '<tr><td colspan="2">Obteniendo datos...</td></tr>';
            if (performanceTable) performanceTable.innerHTML = '<tr><td colspan="2">Obteniendo datos...</td></tr>';
            if (topFlowsTable) topFlowsTable.innerHTML = '<tr><td colspan="4">Obteniendo datos...</td></tr>';
            if (flowsTable) flowsTable.innerHTML = '<tr><td colspan="2">Obteniendo datos...</td></tr>';
            if (analysis) analysis.textContent = 'Obteniendo análisis...';
            if (conclusion) conclusion.textContent = 'Obteniendo conclusión...';

            if (table && data.markets) {
                console.log('[Renderer] Actualizando tabla de estadísticas de mercado');
                table.innerHTML = '';
                const metrics = [
                    { key: 'price', label: 'Precio (USD)', format: v => `$${v.toFixed(2)}` },
                    { key: 'percent_change_24h', label: 'Cambio 24h (%)', format: v => `${v.toFixed(2)}%` },
                    { key: 'market_cap', label: 'Capitalización (USD)', format: v => `$${v.toFixed(2)}` },
                    { key: 'volume_24h', label: 'Volumen 24h (USD)', format: v => `$${v.toFixed(2)}` }
                ];
                metrics.forEach(metric => {
                    if (data.markets[metric.key] !== undefined) {
                        const row = document.createElement('tr');
                        row.innerHTML = `<td>${metric.label}</td><td>${metric.format(data.markets[metric.key])}</td>`;
                        table.appendChild(row);
                        console.log(`[Renderer] Añadida fila para ${metric.label}`);
                    }
                });
            }

            if (lastUpdated && data.markets?.last_updated) {
                console.log('[Renderer] Actualizando última actualización');
                lastUpdated.textContent = new Date(data.markets.last_updated).toLocaleString();
            }

            if (performanceTable && data.yields) {
                console.log('[Renderer] Actualizando tabla de rendimiento');
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
                        console.log(`[Renderer] Añadida fila para ${period.label}`);
                    }
                });
            }

            if (topFlowsTable && data.top_flows) {
                console.log('[Renderer] Actualizando tabla de flujos principales');
                topFlowsTable.innerHTML = '';
                data.top_flows.forEach(flow => {
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${flow.time}</td>
                        <td>$${flow.input_total_usd.toFixed(2)}</td>
                        <td>$${flow.output_total_usd.toFixed(2)}</td>
                        <td>${flow.is_confirmed ? 'Confirmado' : 'Pendiente'}</td>
                    `;
                    topFlowsTable.appendChild(row);
                    console.log(`[Renderer] Añadida fila para flujo en ${flow.time}`);
                });
            }

            if (flowsTable && (data.inflows || data.outflows || data.net_flow)) {
                console.log('[Renderer] Actualizando tabla de flujos');
                flowsTable.innerHTML = '';
                const flows = [
                    { key: 'inflows', label: 'Entradas (BTC)' },
                    { key: 'outflows', label: 'Salidas (BTC)' },
                    { key: 'net_flow', label: 'Flujo Neto (BTC)' }
                ];
                flows.forEach(flow => {
                    if (data[flow.key] !== undefined) {
                        const row = document.createElement('tr');
                        row.innerHTML = `<td>${flow.label}</td><td>${data[flow.key].toFixed(2)}</td>`;
                        flowsTable.appendChild(row);
                        console.log(`[Renderer] Añadida fila para ${flow.label}`);
                    }
                });
            }

            if (priceTrendChart && data.price_history) {
                console.log('[Renderer] Actualizando gráfico de tendencia de precios');
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
                        title: { text: 'Fecha', font: { color: '#cccccc' } },
                        tickfont: { color: '#cccccc' },
                        gridcolor: '#333',
                        range: [startDate, endDate]
                    },
                    yaxis: {
                        title: { text: 'Precio (USD)', font: { color: '#cccccc' } },
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
                console.log('[Renderer] Gráfico de tendencia de precios no actualizado: faltan datos de price_history');
                Plotly.purge(priceTrendChart);
                document.getElementById('priceTrendError').innerHTML = 'No hay datos de historial de precios disponibles';
            }

            if (feesChart && data.fees?.dates && data.fees?.values) {
                console.log('[Renderer] Actualizando gráfico de tarifas');
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
                    console.log('[Renderer] No hay datos de tarifas en el rango seleccionado');
                    document.getElementById('feesError').innerHTML = 'No hay datos de tarifas disponibles para el rango seleccionado';
                    return;
                }

                const trace = {
                    x: filteredDates,
                    y: filteredValues,
                    type: 'scatter',
                    mode: 'lines+markers',
                    name: 'Tarifas de Transacción',
                    line: { color: '#0d6efd', width: 2 },
                    marker: { size: 8, color: '#0d6efd', symbol: 'circle' }
                };
                Plotly.newPlot(feesChart, [trace], {
                    title: {
                        text: 'Tarifas de Transacción',
                        font: { family: 'Arial, sans-serif', size: 18, color: '#ffffff' }
                    },
                    xaxis: {
                        title: { text: 'Fecha', font: { color: '#cccccc' } },
                        tickfont: { color: '#cccccc' },
                        gridcolor: '#333',
                        range: [startDate, endDate]
                    },
                    yaxis: {
                        title: { text: 'Tarifa (USD)', font: { color: '#cccccc' } },
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
                console.log('[Renderer] Gráfico de tarifas no actualizado: faltan datos de tarifas');
                Plotly.purge(feesChart);
                document.getElementById('feesError').innerHTML = 'No hay datos de tarifas disponibles';
            }

            if (analysis && data.analysis) {
                console.log(`[Renderer] Actualizando análisis: ${data.analysis}`);
                analysis.textContent = data.analysis;
            } else {
                console.log('[Renderer] No hay datos de análisis disponibles');
                if (analysis) analysis.textContent = 'No hay análisis disponible';
            }

            if (conclusion && data.conclusion) {
                console.log(`[Renderer] Actualizando conclusión: ${data.conclusion}`);
                conclusion.textContent = data.conclusion;
            } else {
                console.log('[Renderer] No hay datos de conclusión disponibles');
                if (conclusion) conclusion.textContent = 'No hay conclusión disponible';
            }
        } else if (section === 'blackrock') {
            const balancesTable = document.getElementById('blackrock-balancesTableBody');
            const transactionsChart = document.getElementById('blackrock-transactionsChart');
            const fedCorrelationTable = document.getElementById('blackrock-fedCorrelationTableBody');
            const transactionsChartError = document.getElementById('transactionsChartError');

            console.log(`[Renderer] Elementos DOM de BlackRock:`, {
                balancesTable: !!balancesTable,
                transactionsChart: !!transactionsChart,
                fedCorrelationTable: !!fedCorrelationTable,
                transactionsChartError: !!transactionsChartError
            });

            if (balancesTable) balancesTable.innerHTML = '<tr><td colspan="3">Obteniendo datos...</td></tr>';
            if (fedCorrelationTable) fedCorrelationTable.innerHTML = '<tr><td colspan="5">Obteniendo datos...</td></tr>';
            if (transactionsChartError) transactionsChartError.innerHTML = '';

            // Actualizar tabla de saldos
            if (balancesTable && data.balances) {
                console.log('[Renderer] Actualizando tabla de saldos de BlackRock');
                balancesTable.innerHTML = '';
                const tokens = ['BTC', 'ETH', 'USDC'];
                tokens.forEach(token => {
                    if (data.balances[token]) {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${token}</td>
                            <td>${data.balances[token].balance.toFixed(2)}</td>
                            <td>$${data.balances[token].balance_usd.toFixed(2)}</td>
                        `;
                        balancesTable.appendChild(row);
                        console.log(`[Renderer] Añadida fila para ${token}`);
                    }
                });
                if (balancesTable.innerHTML === '') {
                    balancesTable.innerHTML = '<tr><td colspan="3">No hay datos de saldos disponibles</td></tr>';
                }
            } else if (balancesTable) {
                console.log('[Renderer] No hay datos de saldos disponibles');
                balancesTable.innerHTML = '<tr><td colspan="3">No hay datos de saldos disponibles</td></tr>';
            }

            // Actualizar gráfico de transacciones
            if (transactionsChart && data.transactions) {
                console.log('[Renderer] Actualizando gráfico de transacciones de BlackRock');
                const ctx = transactionsChart.getContext('2d');
                if (transactionsChart.chartInstance) {
                    transactionsChart.chartInstance.destroy();
                    console.log('[Renderer] Destruida instancia previa del gráfico de transacciones');
                }

                // Agregar transacciones por fecha y token
                const dates = [...new Set(data.transactions.map(tx => tx.timestamp.split(' ')[0]))].sort();
                const datasets = [];
                const tokenConfigs = [
                    { token: 'BTC', buyColor: '#0d6efd', sellColor: '#dc3545', buyLabel: 'BTC Compras (USD)', sellLabel: 'BTC Ventas (USD)' },
                    { token: 'ETH', buyColor: '#28a745', sellColor: '#ffc107', buyLabel: 'ETH Compras (USD)', sellLabel: 'ETH Ventas (USD)' },
                    { token: 'USDC', buyColor: '#17a2b8', sellColor: '#fd7e14', buyLabel: 'USDC Compras (USD)', sellLabel: 'USDC Ventas (USD)' }
                ];

                tokenConfigs.forEach(config => {
                    const buyData = dates.map(date => {
                        return data.transactions
                            .filter(tx => tx.token === config.token && tx.type === 'buy' && tx.timestamp.startsWith(date))
                            .reduce((sum, tx) => sum + tx.usd_value, 0);
                    });
                    const sellData = dates.map(date => {
                        return data.transactions
                            .filter(tx => tx.token === config.token && tx.type === 'sell' && tx.timestamp.startsWith(date))
                            .reduce((sum, tx) => sum + tx.usd_value, 0);
                    });

                    // Solo añadir datasets si hay datos
                    if (buyData.some(v => v > 0)) {
                        datasets.push({
                            label: config.buyLabel,
                            data: buyData,
                            borderColor: config.buyColor,
                            backgroundColor: `rgba(${parseInt(config.buyColor.slice(1, 3), 16)}, ${parseInt(config.buyColor.slice(3, 5), 16)}, ${parseInt(config.buyColor.slice(5, 7), 16)}, 0.2)`,
                            fill: false,
                            tension: 0.1
                        });
                    }
                    if (sellData.some(v => v > 0)) {
                        datasets.push({
                            label: config.sellLabel,
                            data: sellData,
                            borderColor: config.sellColor,
                            backgroundColor: `rgba(${parseInt(config.sellColor.slice(1, 3), 16)}, ${parseInt(config.sellColor.slice(3, 5), 16)}, ${parseInt(config.sellColor.slice(5, 7), 16)}, 0.2)`,
                            fill: false,
                            tension: 0.1
                        });
                    }
                });

                if (datasets.length === 0) {
                    console.log('[Renderer] No hay datos de transacciones para mostrar');
                    if (transactionsChartError) transactionsChartError.innerHTML = 'No hay datos de transacciones disponibles';
                    return;
                }

                transactionsChart.chartInstance = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: dates,
                        datasets: datasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { labels: { color: '#cccccc' } },
                            title: { display: true, text: 'Actividad de Transacciones (USD)', color: '#cccccc' }
                        },
                        scales: {
                            x: {
                                title: { display: true, text: 'Fecha', color: '#cccccc' },
                                ticks: { color: '#cccccc' },
                                grid: { color: '#333' }
                            },
                            y: {
                                title: { display: true, text: 'Monto (USD)', color: '#cccccc' },
                                ticks: { color: '#cccccc' },
                                grid: { color: '#333' }
                            }
                        }
                    }
                });
                console.log('[Renderer] Gráfico de transacciones creado');
            } else if (transactionsChart) {
                console.log('[Renderer] Gráfico de transacciones no actualizado: faltan datos de transacciones');
                if (transactionsChartError) transactionsChartError.innerHTML = 'No hay datos de transacciones disponibles';
            }

            // Actualizar tabla de correlación con noticias de la FED
            if (fedCorrelationTable && data.fed_news_correlation) {
                console.log('[Renderer] Actualizando tabla de correlación con noticias de BlackRock');
                fedCorrelationTable.innerHTML = '';
                data.fed_news_correlation.forEach(item => {
                    const beforeSummary = item.before.reduce((acc, tx) => {
                        acc[tx.token] = acc[tx.token] || { buy: 0, sell: 0 };
                        acc[tx.token][tx.type] += tx.usd_value;
                        return acc;
                    }, {});
                    const afterSummary = item.after.reduce((acc, tx) => {
                        acc[tx.token] = acc[tx.token] || { buy: 0, sell: 0 };
                        acc[tx.token][tx.type] += tx.usd_value;
                        return acc;
                    }, {});
                    const tokens = ['BTC', 'ETH', 'USDC'];
                    const beforeText = tokens.map(token => 
                        `${token}: $${(beforeSummary[token]?.buy || 0).toFixed(2)} (compra), $${(beforeSummary[token]?.sell || 0).toFixed(2)} (venta)`
                    ).join('; ');
                    const afterText = tokens.map(token => 
                        `${token}: $${(afterSummary[token]?.buy || 0).toFixed(2)} (compra), $${(afterSummary[token]?.sell || 0).toFixed(2)} (venta)`
                    ).join('; ');
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${new Date(item.news_date).toLocaleString()}</td>
                        <td>${item.title}</td>
                        <td>${item.sentiment}</td>
                        <td>${beforeText}</td>
                        <td>${afterText}</td>
                    `;
                    fedCorrelationTable.appendChild(row);
                    console.log(`[Renderer] Añadida fila para noticia en ${item.news_date}`);
                });
                if (fedCorrelationTable.innerHTML === '') {
                    fedCorrelationTable.innerHTML = '<tr><td colspan="5">No hay datos de correlación con noticias disponibles</td></tr>';
                }
            } else if (fedCorrelationTable) {
                console.log('[Renderer] No hay datos de correlación con noticias disponibles');
                fedCorrelationTable.innerHTML = '<tr><td colspan="5">No hay datos de correlación con noticias disponibles</td></tr>';
            }
        }
    } catch (err) {
        console.error(`[Renderer] Error: ${err.message}`);
        if (status) status.innerHTML = `Error: ${err.message}`;
        if (loading) loading.style.display = 'none';
    }
}