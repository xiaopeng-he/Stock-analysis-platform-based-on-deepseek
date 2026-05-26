/**
 * ECharts K线图——加载和渲染分钟级蜡烛图。
 */

// 缓存 chart 实例
let klineChart = null;

async function initKlineChart(stockCode, period) {
    const container = document.getElementById('kline-chart');
    if (!container) return;

    // 初始化或复用实例
    if (!klineChart) {
        klineChart = echarts.init(container);
    }

    // 加载数据
    try {
        const resp = await fetch(`/api/stock/${stockCode}/kline?period=${period}`);
        const data = await resp.json();
        renderKlineChart(data.klines || []);
    } catch(e) {
        console.error('Kline fetch error:', e);
        container.innerHTML = '<div class="loading">K线数据加载失败</div>';
    }

    // 每 60 秒自动刷新
    setInterval(async () => {
        try {
            const resp = await fetch(`/api/stock/${stockCode}/kline?period=${period}`);
            const data = await resp.json();
            if (data.klines && data.klines.length > 0) {
                updateKlineChart(data.klines);
            }
        } catch(e) {}
    }, 60000);
}

// 计算移动平均
function calcMA(data, period) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) { result.push(null); continue; }
        let sum = 0;
        for (let j = i - period + 1; j <= i; j++) sum += data[j];
        result.push(+(sum / period).toFixed(2));
    }
    return result;
}

function renderKlineChart(klines) {
    if (!klineChart || !klines.length) return;

    const isDaily = klines[0].time && klines[0].time.length <= 10;
    const dates = klines.map(k => {
        const t = k.time || '';
        return isDaily ? t.substring(5) : (t.length > 14 ? t.substring(5, 16) : t);
    });
    const ohlc = klines.map(k => [k.open, k.close, k.low, k.high]);
    const volumes = klines.map(k => k.volume);
    const closes = klines.map(k => k.close);

    // 计算均线
    const ma5 = calcMA(closes, 5);
    const ma10 = calcMA(closes, 10);
    const ma20 = calcMA(closes, 20);
    const ma60 = calcMA(closes, 60);

    const option = {
        backgroundColor: '#1a1d29',
        grid: [
            { left: '8%', right: '3%', top: '5%', height: '58%' },
            { left: '8%', right: '3%', top: '72%', height: '16%' }
        ],
        legend: {
            data: ['K线', 'MA5', 'MA10', 'MA20', 'MA60'],
            top: 0, left: 'center',
            textStyle: { color: '#9ca3af', fontSize: 10 },
            itemWidth: 12, itemHeight: 2,
        },
        xAxis: [
            {
                type: 'category', data: dates,
                axisLine: { lineStyle: { color: '#2a2d3a' } },
                axisLabel: { color: '#9ca3af', fontSize: 10, rotate: isDaily ? 0 : 30 },
                gridIndex: 0,
            },
            {
                type: 'category', data: dates,
                axisLine: { lineStyle: { color: '#2a2d3a' } },
                axisLabel: { show: false },
                gridIndex: 1,
            }
        ],
        yAxis: [
            {
                scale: true,
                axisLine: { lineStyle: { color: '#2a2d3a' } },
                axisLabel: { color: '#9ca3af', fontSize: 10 },
                splitLine: { lineStyle: { color: '#1f2230' } },
                gridIndex: 0,
            },
            {
                axisLine: { lineStyle: { color: '#2a2d3a' } },
                axisLabel: { color: '#9ca3af', fontSize: 10 },
                splitLine: { show: false },
                gridIndex: 1,
            }
        ],
        series: [
            {
                name: 'K线', type: 'candlestick', data: ohlc,
                itemStyle: { color: '#ec5a5a', color0: '#47b262', borderColor: '#ec5a5a', borderColor0: '#47b262' },
                xAxisIndex: 0, yAxisIndex: 0, z: 5,
            },
            {
                name: 'MA5', type: 'line', data: ma5,
                smooth: true, symbol: 'none',
                lineStyle: { color: '#f59e0b', width: 1, type: 'solid' },
                xAxisIndex: 0, yAxisIndex: 0, z: 6,
            },
            {
                name: 'MA10', type: 'line', data: ma10,
                smooth: true, symbol: 'none',
                lineStyle: { color: '#3b82f6', width: 1, type: 'solid' },
                xAxisIndex: 0, yAxisIndex: 0, z: 6,
            },
            {
                name: 'MA20', type: 'line', data: ma20,
                smooth: true, symbol: 'none',
                lineStyle: { color: '#8b5cf6', width: 1, type: 'dashed' },
                xAxisIndex: 0, yAxisIndex: 0, z: 6,
            },
            {
                name: 'MA60', type: 'line', data: ma60,
                smooth: true, symbol: 'none',
                lineStyle: { color: '#ec5a5a', width: 1.5, type: 'dotted' },
                xAxisIndex: 0, yAxisIndex: 0, z: 6,
            },
            {
                name: '成交量', type: 'bar', data: volumes,
                itemStyle: { color: p => ohlc[p.dataIndex][1] >= ohlc[p.dataIndex][0] ? '#ec5a5a' : '#47b262' },
                xAxisIndex: 1, yAxisIndex: 1,
            }
        ],
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' },
            backgroundColor: 'rgba(26,29,41,0.95)',
            borderColor: '#2a2d3a',
            textStyle: { color: '#e8e8ed', fontSize: 11 },
        },
        dataZoom: [
            { type: 'inside', xAxisIndex: [0, 1], start: isDaily ? 50 : 70, end: 100 }
        ],
    };

    klineChart.setOption(option, true);
}

function updateKlineChart(klines) {
    if (!klineChart || !klines.length) return;

    const dates = klines.map(k => k.time);
    const ohlc = klines.map(k => [k.open, k.close, k.low, k.high]);
    const volumes = klines.map(k => k.volume);

    klineChart.setOption({
        xAxis: [{ data: dates }, { data: dates }],
        series: [{ data: ohlc }, { data: volumes }]
    });
}

// 窗口大小变化时自适应
window.addEventListener('resize', () => {
    if (klineChart) klineChart.resize();
});
