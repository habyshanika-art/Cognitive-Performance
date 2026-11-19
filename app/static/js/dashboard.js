/**
 * Dashboard Scripts
 * Sidebar toggle (mobile) and Chart.js initialization with baseline band.
 */

document.addEventListener('DOMContentLoaded', function () {
    var sidebar = document.getElementById('dashboardSidebar');
    var toggle = document.getElementById('sidebarToggle');
    var overlay = document.getElementById('sidebarOverlay');

    if (toggle && sidebar) {
        toggle.addEventListener('click', function () {
            sidebar.classList.toggle('open');
            overlay.classList.toggle('show');
        });
    }

    if (overlay) {
        overlay.addEventListener('click', function () {
            if (sidebar) sidebar.classList.remove('open');
            overlay.classList.remove('show');
        });
    }
});

function initDashboardCharts(typingData, reactionData) {
    typingData = typingData || { labels: [], values: [] };
    reactionData = reactionData || { labels: [], values: [] };
    var typingValues = typingData.values || [];
    var reactionValues = reactionData.values || [];

    var chartDefaults = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
            y: { beginAtZero: true, grid: { color: 'rgba(0,0,0,0.05)' } },
            x: { grid: { display: false } }
        }
    };

    var typingCanvas = document.getElementById('typingChart');
    if (typingCanvas && typingValues.length > 0) {
        new Chart(typingCanvas, {
            type: 'line',
            data: {
                labels: typingData.labels || [],
                datasets: [{
                    label: 'WPM',
                    data: typingValues,
                    borderColor: '#1565c0',
                    backgroundColor: 'rgba(21,101,192,0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 5
                }]
            },
            options: chartDefaults
        });
    } else if (typingCanvas) {
        typingCanvas.parentElement.innerHTML =
            '<p class="text-muted-custom text-center py-4">Complete typing tests to see progress.</p>';
    }

    var reactionCanvas = document.getElementById('reactionChart');
    if (reactionCanvas && reactionValues.length > 0) {
        new Chart(reactionCanvas, {
            type: 'line',
            data: {
                labels: reactionData.labels || [],
                datasets: [{
                    label: 'ms',
                    data: reactionValues,
                    borderColor: '#2e7d32',
                    backgroundColor: 'rgba(46,125,50,0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 5
                }]
            },
            options: chartDefaults
        });
    } else if (reactionCanvas) {
        reactionCanvas.parentElement.innerHTML =
            '<p class="text-muted-custom text-center py-4">Complete reaction tests to see progress.</p>';
    }
}

/**
 * Longitudinal chart with baseline band + flagged cycle point colors.
 */
function initCycleTrendChart(cycleData) {
    var canvas = document.getElementById('cycleTrendChart');
    if (!canvas) return;

    cycleData = cycleData || {};
    if (!cycleData.labels || cycleData.labels.length === 0) {
        canvas.parentElement.innerHTML =
            '<p class="text-muted-custom text-center py-4">Complete a full assessment cycle to see longitudinal trends.</p>';
        return;
    }

    var n = cycleData.labels.length;
    var baseline = cycleData.baseline || {};
    var flagged = cycleData.flagged || [];
    var overallScores = cycleData.overall_scores || [];

    var pointColors = overallScores.map(function (_, i) {
        return flagged[i] ? '#c62828' : '#6a1b9a';
    });
    var pointRadii = overallScores.map(function (_, i) {
        return flagged[i] ? 8 : 6;
    });
    var datasets = [
        {
            label: 'Overall Score',
            data: overallScores,
            borderColor: '#6a1b9a',
            backgroundColor: 'rgba(106,27,154,0.08)',
            fill: false,
            tension: 0.3,
            pointRadius: pointRadii,
            pointBackgroundColor: pointColors,
            pointBorderColor: pointColors,
            yAxisID: 'y',
            order: 1,
        },
        {
            label: 'Typing WPM',
            data: cycleData.typing_speeds || [],
            borderColor: '#1565c0',
            borderDash: [4, 4],
            tension: 0.3,
            pointRadius: 3,
            yAxisID: 'y1',
            order: 2,
        },
        {
            label: 'Reaction (ms)',
            data: cycleData.reaction_times || [],
            borderColor: '#2e7d32',
            borderDash: [4, 4],
            tension: 0.3,
            pointRadius: 3,
            yAxisID: 'y2',
            order: 3,
        },
    ];

    if (cycleData.memory_scores && cycleData.memory_scores.some(function (v) { return v > 0; })) {
        datasets.push({
            label: 'Memory',
            data: cycleData.memory_scores,
            borderColor: '#ef6c00',
            borderDash: [2, 2],
            tension: 0.3,
            pointRadius: 3,
            yAxisID: 'y',
            order: 4,
        });
    }

    if (cycleData.concentration_scores && cycleData.concentration_scores.some(function (v) { return v > 0; })) {
        datasets.push({
            label: 'Concentration',
            data: cycleData.concentration_scores,
            borderColor: '#00838f',
            borderDash: [6, 3],
            tension: 0.3,
            pointRadius: 3,
            yAxisID: 'y',
            order: 5,
        });
    }

    // Baseline band as two lines (high/low) with fill between via a third dataset trick
    if (baseline.ready && baseline.overall_low != null && baseline.overall_high != null) {
        var lowBand = [];
        var highBand = [];
        for (var i = 0; i < n; i++) {
            lowBand.push(baseline.overall_low);
            highBand.push(baseline.overall_high);
        }
        datasets.unshift({
            label: 'Baseline high',
            data: highBand,
            borderColor: 'rgba(21,101,192,0.35)',
            backgroundColor: 'rgba(21,101,192,0.12)',
            pointRadius: 0,
            fill: '+1',
            tension: 0,
            yAxisID: 'y',
            order: 10,
        });
        datasets.unshift({
            label: 'Baseline low',
            data: lowBand,
            borderColor: 'rgba(21,101,192,0.35)',
            backgroundColor: 'transparent',
            pointRadius: 0,
            fill: false,
            tension: 0,
            yAxisID: 'y',
            order: 11,
        });
    }

    new Chart(canvas, {
        type: 'line',
        data: {
            labels: cycleData.labels,
            datasets: datasets,
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: 'index', intersect: false },
            plugins: {
                legend: { position: 'bottom' },
                tooltip: {
                    callbacks: {
                        afterBody: function (items) {
                            var idx = items[0] && items[0].dataIndex;
                            if (idx == null) return '';
                            var lines = [];
                            if (flagged[idx]) lines.push('⚑ Flagged vs baseline');
                            if (cycleData.deviations && cycleData.deviations[idx] != null) {
                                lines.push('Overall deviation: ' + cycleData.deviations[idx]);
                            }
                            return lines;
                        }
                    }
                }
            },
            scales: {
                y: {
                    type: 'linear',
                    position: 'left',
                    title: { display: true, text: 'Score' },
                    grid: { color: 'rgba(0,0,0,0.05)' },
                },
                y1: {
                    type: 'linear',
                    position: 'right',
                    title: { display: true, text: 'WPM' },
                    grid: { drawOnChartArea: false },
                },
                y2: {
                    type: 'linear',
                    position: 'right',
                    display: false,
                },
                x: { grid: { display: false } },
            },
        },
    });
}
