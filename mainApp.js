//var settingsCookie = getCookie('settingsCookie');
const NEWS_SOURCE_COOKIE_DAYS = 365; // 你也可以改成 180 / 730
var settingsCookie = {};
if (settings) {
    try {
        settingsCookie = JSON.parse(settings);
    } catch (e) {
        settingsCookie = {};
    }
}
initializeCheckboxes();
function getSettingsCookieObj() {
  const raw = getCookie('settingsCookie');
  if (!raw) return null;
  try { return JSON.parse(raw); } catch (e) { return null; }
}

function ensureGuestDefaultSettings() {
  // 只对游客做（userPhone 为空就是游客）
  if (userPhone) return;

  let obj = getSettingsCookieObj();
  if (obj) return; // 已有就不动

  const defaults = {
    voice: 1,
    voiceConcept: 0,
    popup: 1,
    voiceKeyword: 0,
    popupKeyword: 0,
    highlightKeyword: 0,
    hiddenRelated: 0,
    onlyShowKeywords: 0,
    keywords: '',
    keywordsRemove: '',
    speakLenght: 30
  };

  setCookie('settingsCookie', JSON.stringify(defaults), 7);

  // 语速 cookie 也给个默认，避免后续 Number(...) 变 NaN
  if (!getCookie('speakRate')) {
    document.cookie = "speakRate=1.75; path=/; max-age=31536000";
  }
}

ensureGuestDefaultSettings();

// 让全局 settingsCookie 真正指向“cookie对象”
settingsCookie = getSettingsCookieObj() || {};

// if(!settingsCookie){
//     settingsCookie = settings;
// }
var categorySetting = getCookie('newsSourceSelections');
categorySetting = categorySetting ? JSON.parse(categorySetting) : [];
if(settingsCookie){
    //settingsCookie = JSON.parse(settingsCookie); // 将字符串解析为对象
    if(settingsCookie['hiddenRelated'] == '1'){
        // 创建一个 <style> 元素
        const style = document.createElement('style');
        // 定义 CSS 规则，隐藏所有具有 'related-news' 类的元素
        style.textContent = `
            .related-news {
                display: none !important;
            }
        `;
        // 将 <style> 元素添加到 <head> 中，使样式生效
        document.head.appendChild(style);
    }
    
    // 确保 settingsCookie 和 keywords 存在，并且 keywords 是一个非空字符串
    if (
        settingsCookie['onlyShowKeywords'] == '1' &&
        settingsCookie['keywords'] &&
        typeof settingsCookie['keywords'] === 'string' &&
        settingsCookie['keywords'].trim() != ''
    ) {
        // 获取 ul 元素，id 为 'news-list'
        const newsList = document.getElementById('news-list');
        
        // 如果 ul 元素存在
        if (newsList) {
            // 获取所有具有 class 'recent-news-item' 和 'flexbox' 的 li 元素
            const listItems = newsList.querySelectorAll('li.recent-news-item.flexbox');
            
            // 将关键词字符串分割成数组，并去除多余的空格
            const keywordsArray = settingsCookie['keywords']
                .split(',')
                .map(keyword => keyword.trim())
                .filter(keyword => keyword != '');
            
            // 遍历每个 li 元素
            listItems.forEach(li => {
                // 获取新闻的 categoryId
                const categoryId = parseInt(li.dataset.categoryId, 10); // 使用 data-category-id 属性
    
                // 如果 categoryId 为 1，则直接保留该新闻项，跳过关键词过滤
                if (categoryId === 1) {
                    return;
                }
    
                // 获取新闻内容的文本
                const titleElement = li.querySelector('.news-content .word-ellipsis3'); // 新闻标题
                const contentElement = li.querySelector('.news-content p'); // 新闻内容
                
                // 拼接标题和内容的文本
                const textContent = (titleElement ? titleElement.innerText.trim() : '') + 
                                   ' ' + 
                                   (contentElement ? contentElement.innerText.trim() : '');
    
                // 检查是否包含任意一个关键词（不区分大小写）
                const includesKeyword = keywordsArray.some(keyword => 
                    textContent.toLowerCase().includes(keyword.toLowerCase())
                );
                
                // 如果不包含任何关键词，则移除该 li 元素
                if (!includesKeyword) {
                    li.remove();
                }
            });
        }
    }
}



function getCookie(name) {
    var nameEQ = name + "=";
    var ca = document.cookie.split(';');
    for (var i = 0; i < ca.length; i++) {
        var c = ca[i];
        while (c.charAt(0) === ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
}

// <!--处理搜索-->
function search(){
    // 获取 input 元素的值
    const keywords = document.getElementById("searchKeywords").value;
    
    // 构造新的 URL
    const url = `https://search.guzhang.com/search?keywords=${encodeURIComponent(keywords)}&keepAll=n&page=1`;
    
    // 在新窗口中打开构造的 URL
    window.open(url, '_blank');
}

// <!--成交额折线图代码-->
let lineChartInstance = null;
// 定义请求数据的函数
function fetchChartData() {
    // 发送请求以获取 JSON 数据
    fetch(`../static/json/chengjiaoe.json?t=${new Date().getTime()}`)
        .then(response => response.json())
        .then(data => {
            // 处理返回的数据
            const jsonData = data;
            const currentTotal = Math.round(jsonData.current.total);
            const previousTotal = Math.round(jsonData.previous.total);
            const previousPreviousTotal = Math.round(jsonData.previousPrevious.total);

            const diffPrevious = Math.round(currentTotal - previousTotal);
            const diffPreviousPrevious = Math.round(currentTotal - previousPreviousTotal);
            const predictionData = Math.round(jsonData.preData);

            const currValElement = document.getElementById('currVal');
            currValElement.innerText = `${currentTotal}亿`;
            currValElement.style.color = 'red';

            const preValElement = document.getElementById('preVal');
            preValElement.innerText = `${diffPrevious}亿`;
            preValElement.style.color = diffPrevious >= 0 ? 'red' : 'green';

            const prePreValElement = document.getElementById('prePreVal');
            prePreValElement.innerText = `${diffPreviousPrevious}亿`;
            prePreValElement.style.color = diffPreviousPrevious >= 0 ? 'red' : 'green';
            
            const preDataElement = document.getElementById('preData');
            preDataElement.innerText = `${predictionData}亿`;
            preDataElement.style.color = 'red';

            const filterData = (arr) => {
                return arr.filter(item => {
                    const time = new Date(item.time * 1000);
                    const hours = time.getHours();
                    const minutes = time.getMinutes();
                    const timeString = `${hours}:${minutes < 10 ? '0' : ''}${minutes}`;
                    return !(timeString >= '11:30' && timeString < '13:00');
                });
            };

            const filteredCurrentArr = filterData(jsonData.currentArr || []);
            const filteredPreviousArr = filterData(jsonData.previousArr || []);
            const filteredPreviousPreviousArr = filterData(jsonData.previousPreviousArr || []);

            const maxLength = Math.max(filteredCurrentArr.length, filteredPreviousArr.length, filteredPreviousPreviousArr.length);
            const labels = Array.from({ length: maxLength }, (_, i) => {
                const time = filteredCurrentArr[i]?.time || filteredPreviousArr[i]?.time || filteredPreviousPreviousArr[i]?.time;
                if (time) {
                    const date = new Date(time * 1000);
                    const hours = date.getHours();
                    const minutes = date.getMinutes();
                    return `${hours}:${minutes < 10 ? '0' : ''}${minutes}`;
                }
                return '';
            });

            const fillData = (arr) => {
                const data = Array(maxLength).fill(null);
                arr.forEach((item, i) => {
                    data[i] = Math.round(parseFloat(item.total));
                });
                return data;
            };

            const dataCurrent = fillData(filteredCurrentArr);
            const dataPrevious = fillData(filteredPreviousArr);
            const dataPreviousPrevious = fillData(filteredPreviousPreviousArr);

            // 销毁之前的图表实例（如果存在）
            if (lineChartInstance) {
                lineChartInstance.destroy();
            }

            const ctx = document.getElementById('lineChart').getContext('2d');
            let lastDisplayedLabel = '';
            lineChartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: '今日',
                            data: dataCurrent,
                            borderColor: 'rgba(247, 79, 67, 1)',
                            backgroundColor: 'rgba(247, 79, 67, 1)',
                            fill: false,
                            pointRadius: 0,
                            pointHoverRadius: 0,
                            tension: 0.1,
                            borderWidth: 2
                        },
                        {
                            label: '昨日',
                            data: dataPrevious,
                            borderColor: 'rgba(123, 133, 168, 1)',
                            backgroundColor: 'rgba(123, 133, 168, 1)',
                            fill: false,
                            pointRadius: 0,
                            pointHoverRadius: 0,
                            tension: 0.1,
                            borderWidth: 2
                        },
                        {
                            label: '前日',
                            data: dataPreviousPrevious,
                            borderColor: 'rgba(210, 210, 210, 1)',
                            backgroundColor: 'rgba(210, 210, 210, 1)',
                            fill: false,
                            pointRadius: 0,
                            pointHoverRadius: 0,
                            tension: 0.1,
                            borderWidth: 2
                        }
                    ]
                },
                options: {
                    interaction: {
                        mode: 'index',
                        intersect: false,
                        axis: 'x'
                    },
                    scales: {
                        x: {
                            title: {
                                display: false,
                                text: '时间'
                            },
                            grid: {
                                display: false,
                            },
                            ticks: {
                                autoSkip: false,
                                maxRotation: 0,
                                padding: 10,
                                minRotation: 0,
                                callback: function (value, index, ticks) {
                                    const label = this.getLabelForValue(value).slice(0, 5);
                                    const displayLabels = ['9:30', '10:00', '10:30', '11:00', '13:00', '13:30', '14:00', '14:30', '15:00'];
                                    if (label === '15:00' && lastDisplayedLabel === '15:00') {
                                        return ''; // 如果已经显示了一个 '15:00' 标签，就不再显示
                                    }
                                    
                                    if (displayLabels.includes(label)) {
                                        lastDisplayedLabel = label;
                                        return label;
                                    } else {
                                        return '';
                                    }
                                }
                            }
                        },
                        y: {
                            beginAtZero: true,
                            title: {
                                display: false,
                                text: '成交额 (亿)'
                            },
                            ticks: {
                                maxTicksLimit: 7,
                            },
                        }
                    },
                    plugins: {
                        title: {
                            display: false,
                            text: 'A股市场成交额走势'
                        },
                        tooltip: {
                            mode: 'index',
                            intersect: false
                        },
                        legend: {
                            display: true,
                            position: 'bottom',
                            labels: {
                                boxWidth: 15,
                                boxHeight: 1,
                                font: {
                                    size: 12
                                },
                                padding: 20
                            }
                        }
                    }
                },
                plugins: [{
                    afterDraw: chart => {
                        if (chart.tooltip && chart.tooltip._active && chart.tooltip._active.length) {
                            const ctx = chart.ctx;
                            ctx.save();
                            const activePoint = chart.tooltip._active[0];
                            if (activePoint) {
                                ctx.beginPath();
                                ctx.moveTo(activePoint.element.x, chart.chartArea.top);
                                ctx.lineTo(activePoint.element.x, chart.chartArea.bottom);
                                ctx.lineWidth = 1;
                                ctx.strokeStyle = 'rgba(0, 0, 0, 0.1)';
                                ctx.stroke();
                                ctx.restore();
                            }
                        }
                    }
                }]
            });
        })
        .catch(error => console.error('Error fetching data:', error));
}
// 调用函数以获取数据并渲染图表
fetchChartData();
// 每分钟调用一次
setInterval(fetchChartData, 60000);

//<!--Chart.js 柱状图代码-->
var ctx = document.getElementById('zdfbChart').getContext('2d');
// 数据
var labels = [
    "st涨停", "涨停", "10%~20%", "9%~10%", "8%~9%", "7%~8%", "6%~7%", "5%~6%", "4%~5%", 
    "3%~4%", "2%~3%", "1%~2%", "0%~1%", "0%", "-1%~0%", "-2%~-1%", "-3%~-2%", "-4%~-3%", 
    "-5%~-4%", "-6%~-5%", "-7%~-6%", "-8%~-7%", "-9%~-8%", "-10%~-9%", "-20%~-10%", "跌停", "st跌停"
];
// 颜色数组，根据标签和数据值决定颜色
var backgroundColors = labels.map((label, index) => {
    if (label.includes("-") || label === "跌停" || label === "st跌停") {
        return "rgba(24, 166, 107)"; // 绿色 (下跌)
    } else if (label === "0%") {
        return "rgba(153, 153, 153)"; // 灰色 (平盘)
    } else {
        return "rgba(242,86,78)"; // 红色 (上涨)
    }
});

var borderColors = backgroundColors;
var zdfbChart = new Chart(ctx, {
    type: 'bar',
    data: {
        labels: labels,
        datasets: [{
            label: '数量',
            data: [],
            backgroundColor: backgroundColors,
            borderColor: borderColors,
            borderWidth: 1
        }]
    },
    options: {
        indexAxis: 'y', // 使图表横向展示
        scales: {
            x: {
                grid: {
                    display: false // 隐藏X轴的网格
                },
                max: function (context) {
                    const chartData = context.chart.data.datasets[0].data;
                    const maxValue = Math.max(...chartData);
                    return Math.ceil(maxValue * 1.1); // 让 maxValue 比实际最大值大 10%
                }
            },
            y: {
                beginAtZero: true,
                grid: {
                    display: false // 隐藏Y轴的网格
                }
            }
        },
        plugins: {
            legend: {
                display: false
            },
            title: {
                display: false,
                text: ''
            },
            datalabels: {  // 添加 datalabels 插件配置
                align: 'end',  // 使标签对齐到柱子顶部
                anchor: 'end',  // 使标签定位到柱子顶部
                color: 'rgba(128, 128, 128, 0.7)',  // 设置标签颜色为淡灰色
                font: {
                    weight: 'normal',  // 不加粗
                    size: 12  // 设置字体大小为 12px
                }
            }
        }
    },
    plugins: [ChartDataLabels]  // 启用 datalabels 插件
});
// 定时每分钟请求一次数据并更新图表和显示内容
function fetchAndUpdateData() {
    fetch(`../static/json/zdf.json?t=${new Date().getTime()}`)
        .then(response => response.json())
        .then(data => {
            const newData = data.data;

            // 按照翻转后的 labels 顺序获取 newData 对应的值
            const updatedData = labels.map(label => newData[label] || 0);  // 如果 newData[label] 不存在则默认为 0

            zdfbChart.data.datasets[0].data = updatedData;  // 更新图表数据
            zdfbChart.update();  // 更新图表显示

            // 更新页面中的上涨、下跌、平盘数量
            document.getElementById('contUp').innerText = `上涨: ${data.count.up} `;
            document.getElementById('contDown').innerText = `下跌: ${data.count.down} `;
            document.getElementById('contNoChange').innerText = `平盘: ${data.count.unchanged} `;
        })
        .catch(error => {
            console.error('Error fetching data:', error);
        });
}

// 初始加载数据
fetchAndUpdateData();
// 每分钟调用一次
setInterval(fetchAndUpdateData, 60000);
let lastSpeakTime = 0; // 初始化全局变量，用于记录上次播报的时间戳
const speakInterval = 2000; // 设置播报时间间隔，单位为毫秒，这里设置为5秒

//<!-- 添加 WebSocket 连接的 JavaScript 代码 -->
let latestNewsSyncInFlight = false;
let reconnectTimer = null;
let autoReloadTimer = null;
let autoReloadAt = 0;
const AUTO_RELOAD_VISIBLE_MIN_DELAY = 15000;
const AUTO_RELOAD_VISIBLE_MAX_DELAY = 75000;
const AUTO_RELOAD_HIDDEN_MIN_DELAY = 120000;
const AUTO_RELOAD_HIDDEN_MAX_DELAY = 600000;
const AUTO_RELOAD_COOLDOWN = 60000;
const AUTO_RELOAD_SESSION_KEY = 'guzhang_auto_reload_at';

function getLastAutoReloadAt() {
    try {
        return parseInt(sessionStorage.getItem(AUTO_RELOAD_SESSION_KEY) || '0', 10) || 0;
    } catch (e) {
        return 0;
    }
}

function markAutoReload(at) {
    try {
        sessionStorage.setItem(AUTO_RELOAD_SESSION_KEY, String(at));
    } catch (e) {
    }
}

function getRandomDelay(minDelay, maxDelay) {
    const safeMin = Math.max(0, parseInt(minDelay, 10) || 0);
    const safeMax = Math.max(safeMin, parseInt(maxDelay, 10) || safeMin);
    return Math.floor(Math.random() * (safeMax - safeMin + 1)) + safeMin;
}

function scheduleAutoReload(reason, options) {
    const opts = options || {};
    const now = Date.now();
    const lastAutoReloadAt = getLastAutoReloadAt();
    if (lastAutoReloadAt > 0 && now - lastAutoReloadAt < AUTO_RELOAD_COOLDOWN) {
        return;
    }

    const isHidden = document.visibilityState === 'hidden';
    let minDelay = Number.isFinite(opts.minDelay)
        ? opts.minDelay
        : AUTO_RELOAD_VISIBLE_MIN_DELAY;
    let maxDelay = Number.isFinite(opts.maxDelay)
        ? opts.maxDelay
        : AUTO_RELOAD_VISIBLE_MAX_DELAY;

    if (isHidden) {
        minDelay = Math.max(minDelay, AUTO_RELOAD_HIDDEN_MIN_DELAY);
        maxDelay = Math.max(maxDelay, AUTO_RELOAD_HIDDEN_MAX_DELAY);
    }

    const delay = getRandomDelay(minDelay, maxDelay);
    const targetAt = now + delay;

    if (autoReloadAt > 0 && autoReloadAt <= targetAt) {
        return;
    }

    if (autoReloadTimer) {
        clearTimeout(autoReloadTimer);
    }

    autoReloadAt = targetAt;
    autoReloadTimer = setTimeout(function () {
        const executeAt = Date.now();
        autoReloadTimer = null;
        autoReloadAt = 0;

        const latestAutoReloadAt = getLastAutoReloadAt();
        if (latestAutoReloadAt > 0 && executeAt - latestAutoReloadAt < AUTO_RELOAD_COOLDOWN) {
            return;
        }

        markAutoReload(executeAt);
        location.reload();
    }, delay);

    console.log(`Auto reload scheduled in ${Math.round(delay / 1000)}s (${reason || 'unknown'})`);
}

document.addEventListener('visibilitychange', function () {
    if (document.visibilityState !== 'visible' || autoReloadAt <= 0) {
        return;
    }

    const remaining = autoReloadAt - Date.now();
    if (remaining > AUTO_RELOAD_VISIBLE_MAX_DELAY) {
        scheduleAutoReload('page-visible');
    }
});

function getWebSocketConfig() {
    const config = window.__NEWS_WS_CONFIG__ || {};
    const scheme = config.scheme && config.scheme !== 'auto'
        ? config.scheme
        : (window.location.protocol === 'https:' ? 'wss' : 'ws');

    return {
        scheme: scheme,
        host: config.host || window.location.hostname,
        port: Number(config.port) || 9508,
        path: config.path || '/'
    };
}

function buildWebSocketUrl() {
    const config = getWebSocketConfig();
    const separator = config.path.indexOf('?') === -1 ? '?' : '&';
    return `${config.scheme}://${config.host}:${config.port}${config.path}${separator}token=${encodeURIComponent(encryptedToken)}`;
}

function getLatestNewsCtime() {
    let latestCtime = 0;
    document.querySelectorAll('#news-list .ptime').forEach(function (item) {
        const value = parseInt(item.textContent || item.innerText || '0', 10);
        if (!Number.isNaN(value) && value > latestCtime) {
            latestCtime = value;
        }
    });
    return latestCtime;
}

function getNewsTimelineValue(item) {
    if (!item || typeof item !== 'object') {
        return 0;
    }

    const directTimelineSource =
        typeof item.ptime_show !== 'undefined' && item.ptime_show !== null && item.ptime_show !== ''
            ? item.ptime_show
            : item.ctime;
    const directTimeline = parseInt(directTimelineSource || 0, 10);
    if (!Number.isNaN(directTimeline) && directTimeline > 0) {
        return directTimeline;
    }

    if (item.ptime) {
        const parsedTime = new Date(String(item.ptime).replace(/-/g, '/')).getTime();
        if (!Number.isNaN(parsedTime) && parsedTime > 0) {
            return Math.floor(parsedTime / 1000);
        }
    }

    return 0;
}

function syncLatestNews() {
    if (latestNewsSyncInFlight) {
        return;
    }

    const latestNewsCtime = getLatestNewsCtime();
    if (latestNewsCtime <= 0) {
        return;
    }

    latestNewsSyncInFlight = true;
    const payload = new URLSearchParams();
    payload.set('type', 'latestNews');
    payload.set('ctime', String(latestNewsCtime));

    fetch('index', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        },
        body: payload.toString()
    })
    .then(function (response) {
        return response.json();
    })
    .then(function (data) {
        const hasNewerTopLevelNews = data.status === 'ok'
            && Array.isArray(data.data)
            && data.data.some(function (item) {
                return !getNewsParentId(item) && getNewsTimelineValue(item) > latestNewsCtime;
            });

        if (hasNewerTopLevelNews) {
            scheduleAutoReload('latest-news-sync', {
                minDelay: 10000,
                maxDelay: 45000
            });
        }
    })
    .catch(function (error) {
        console.error('Latest news sync failed: ', error);
    })
    .finally(function () {
        latestNewsSyncInFlight = false;
    });
}

function isVisibleNewsItem(item) {
    if (!item) {
        return false;
    }

    return window.getComputedStyle(item).display !== 'none';
}

const PENDING_TOP_NEWS_THRESHOLD = 160;
const pendingTopNewsItems = [];
let pendingTopNewsNotice = null;

function isNearNewsListTop() {
    if (window.scrollY <= PENDING_TOP_NEWS_THRESHOLD) {
        return true;
    }

    const newsList = document.getElementById('news-list');
    if (!newsList) {
        return true;
    }

    const listRect = newsList.getBoundingClientRect();
    return listRect.top >= -PENDING_TOP_NEWS_THRESHOLD;
}

function ensurePendingTopNewsNotice() {
    if (pendingTopNewsNotice) {
        return pendingTopNewsNotice;
    }

    pendingTopNewsNotice = document.createElement('button');
    pendingTopNewsNotice.type = 'button';
    pendingTopNewsNotice.style.cssText = [
        'position:fixed',
        'top:72px',
        'left:50%',
        'transform:translateX(-50%)',
        'z-index:9999',
        'display:none',
        'border:0',
        'border-radius:16px',
        'padding:7px 16px',
        'background:#373d53',
        'color:#fff',
        'font-size:13px',
        'line-height:18px',
        'box-shadow:0 2px 8px rgba(0,0,0,0.16)',
        'cursor:pointer'
    ].join(';');
    pendingTopNewsNotice.addEventListener('click', function () {
        flushPendingTopNewsItems(true);
    });

    document.body.appendChild(pendingTopNewsNotice);
    return pendingTopNewsNotice;
}

function updatePendingTopNewsNotice() {
    const notice = ensurePendingTopNewsNotice();
    const count = pendingTopNewsItems.length;

    if (count <= 0) {
        notice.style.display = 'none';
        return;
    }

    notice.textContent = `有 ${count} 条新新闻，点击查看`;
    notice.style.display = 'block';
}

function schedulePinnedNewsExpiry(newsItem) {
    if (!newsItem || !newsItem.classList.contains('pinned-news')) {
        return;
    }

    const pinnedTimeNum = Number(pinnedTime);
    if (!Number.isFinite(pinnedTimeNum) || pinnedTimeNum <= 0) {
        return;
    }

    setTimeout(() => {
        newsItem.classList.remove('pinned-news');
        sortNewsListItems();
    }, pinnedTimeNum * 1000);
}

function insertTopNewsItem(newsItem, isPinned) {
    const newsList = document.getElementById('news-list');
    if (!newsList || !newsItem) {
        return false;
    }

    if (isPinned) {
        newsList.insertBefore(newsItem, newsList.firstChild);
    } else {
        const pinnedNewsItems = newsList.querySelectorAll('.pinned-news');
        if (pinnedNewsItems.length > 0) {
            const lastPinnedNewsItem = pinnedNewsItems[pinnedNewsItems.length - 1];
            newsList.insertBefore(newsItem, lastPinnedNewsItem.nextSibling);
        } else {
            newsList.insertBefore(newsItem, newsList.firstChild);
        }
    }

    normalizeGroupedNewsItem(newsItem);
    schedulePinnedNewsExpiry(newsItem);
    return true;
}

function enqueuePendingTopNewsItem(newsItem, isPinned) {
    if (!newsItem) {
        return;
    }

    pendingTopNewsItems.push({
        aid: String(newsItem.getAttribute('data-aid') || ''),
        isPinned: !!isPinned,
        node: newsItem
    });
    updatePendingTopNewsNotice();
}

function flushPendingTopNewsItems(scrollToTop) {
    if (pendingTopNewsItems.length === 0) {
        updatePendingTopNewsNotice();
        return;
    }

    if (scrollToTop) {
        window.scrollTo({
            top: 0,
            left: 0,
            behavior: 'auto'
        });
    }

    const queuedItems = pendingTopNewsItems.splice(0);
    queuedItems.forEach(entry => {
        insertTopNewsItem(entry.node, entry.isPinned);
    });

    sortNewsListItems();
    reviveHiddenParents();
    updatePendingTopNewsNotice();
}

function flushPendingTopNewsItemsIfNearTop() {
    if (pendingTopNewsItems.length > 0 && isNearNewsListTop()) {
        flushPendingTopNewsItems(false);
    }
}

function getVisibleOrphanParentItem(parentId) {
    const orphanParents = document.querySelectorAll(`#news-list li[data-orphan-parent="${parentId}"]`);
    for (const item of orphanParents) {
        if (isVisibleNewsItem(item)) {
            return item;
        }
    }

    return null;
}

function getVisibleParentNewsItem(parentId) {
    const directParent = document.querySelector(`#news-list li[data-aid="${parentId}"]`);
    if (isVisibleNewsItem(directParent)) {
        return directParent;
    }

    return getVisibleOrphanParentItem(parentId);
}

function getVisibleParentNewsContent(parentId) {
    const parentItem = getVisibleParentNewsItem(parentId);
    return parentItem ? parentItem.querySelector('.news-content') : null;
}

const RELATED_NEWS_TITLE = '相似文章';

function getCanonicalParentNewsContent(parentId) {
    const directParent = document.querySelector(`#news-list li[data-aid="${parentId}"]:not(.revived-news-item)`);
    return directParent ? directParent.querySelector('.news-content') : null;
}

function parseNewsTimestamp(value) {
    if (value === undefined || value === null || value === '') {
        return 0;
    }

    if (typeof value === 'number' && Number.isFinite(value)) {
        return value > 1000000000000 ? Math.floor(value / 1000) : Math.floor(value);
    }

    const raw = String(value).trim();
    if (!raw) {
        return 0;
    }

    if (/^\d+$/.test(raw)) {
        const numeric = parseInt(raw, 10);
        return raw.length > 10 ? Math.floor(numeric / 1000) : numeric;
    }

    const parsed = new Date(raw.replace(/-/g, '/')).getTime();
    return Number.isNaN(parsed) ? 0 : Math.floor(parsed / 1000);
}

function formatRelatedNewsText(timeValue, comefrom, title) {
    const timeLabel = formatTimestampToTime(String(timeValue || '')) || '';
    return `${timeLabel}【${comefrom || ''}】${title || ''}`;
}

function sortRelatedNewsLinksAscending(newsListDiv) {
    if (!newsListDiv) {
        return;
    }

    const links = Array.from(newsListDiv.querySelectorAll('a.news-item'));
    const uniqueLinks = [];
    const seenAids = new Set();

    links
        .sort((a, b) => parseNewsTimestamp(a.getAttribute('data-ptime')) - parseNewsTimestamp(b.getAttribute('data-ptime')))
        .forEach(link => {
            const aid = String(link.getAttribute('data-aid') || '');
            if (aid && seenAids.has(aid)) {
                link.remove();
                return;
            }

            if (aid) {
                seenAids.add(aid);
            }

            link.innerHTML = formatRelatedNewsText(
                link.getAttribute('data-ptime') || '',
                link.getAttribute('data-comefrom') || '',
                link.getAttribute('data-title') || ''
            );
            uniqueLinks.push(link);
        });

    uniqueLinks.forEach(link => {
        newsListDiv.appendChild(link);
    });
}

function insertRelatedNewsLinkByTime(newsListDiv, linkNode) {
    if (!newsListDiv || !linkNode) {
        return;
    }

    const linkTimestamp = parseNewsTimestamp(linkNode.getAttribute('data-ptime'));
    const insertBeforeLink = Array.from(newsListDiv.querySelectorAll('a.news-item')).find(link => {
        return parseNewsTimestamp(link.getAttribute('data-ptime')) > linkTimestamp;
    });

    if (insertBeforeLink) {
        newsListDiv.insertBefore(linkNode, insertBeforeLink);
        return;
    }

    newsListDiv.appendChild(linkNode);
}

function ensureRelatedNewsList(parentNewsContent) {
    let relatedNewsDiv = parentNewsContent.querySelector('.related-news');
    if (!relatedNewsDiv) {
        relatedNewsDiv = document.createElement('div');
        relatedNewsDiv.className = 'related-news';

        const titleDiv = document.createElement('div');
        titleDiv.className = 'title';
        titleDiv.innerText = RELATED_NEWS_TITLE;

        const newsListDiv = document.createElement('div');
        newsListDiv.className = 'related-news-list';

        relatedNewsDiv.appendChild(titleDiv);
        relatedNewsDiv.appendChild(newsListDiv);
        parentNewsContent.appendChild(relatedNewsDiv);

        return newsListDiv;
    }

    let titleDiv = relatedNewsDiv.querySelector('.title');
    if (!titleDiv) {
        titleDiv = document.createElement('div');
        titleDiv.className = 'title';
        relatedNewsDiv.insertBefore(titleDiv, relatedNewsDiv.firstChild || null);
    }
    titleDiv.innerText = RELATED_NEWS_TITLE;

    let newsListDiv = relatedNewsDiv.querySelector('.related-news-list');
    if (!newsListDiv) {
        const divChildren = Array.from(relatedNewsDiv.children).filter(function (child) {
            return child.tagName === 'DIV';
        });
        newsListDiv = divChildren[1] || document.createElement('div');
        newsListDiv.classList.add('related-news-list');
        if (!newsListDiv.parentNode) {
            relatedNewsDiv.appendChild(newsListDiv);
        }
    }

    return newsListDiv;
}

function appendRelatedNewsToParent(parentNewsContent, newData) {
    const newsListDiv = ensureRelatedNewsList(parentNewsContent);
    if (newsListDiv.querySelector(`a[data-aid="${newData.aid}"]`)) {
        sortRelatedNewsLinksAscending(newsListDiv);
        return;
    }

    const similarNewsItem = document.createElement('a');
    similarNewsItem.className = 'news-item word-ellipsis';
    similarNewsItem.title = stripHtmlTags(newData.title || '');
    similarNewsItem.innerHTML = formatRelatedNewsText(newData.ptime, newData.comefrom, newData.title);
    similarNewsItem.setAttribute('data-aid', newData.aid);
    similarNewsItem.setAttribute('data-parent', getNewsParentId(newData));
    similarNewsItem.setAttribute('data-category-id', newData.categoryId || '');
    similarNewsItem.setAttribute('data-ptime', newData.ptime || '');
    similarNewsItem.setAttribute('data-comefrom', newData.comefrom || '');
    similarNewsItem.setAttribute('data-title', newData.title || '');
    similarNewsItem.setAttribute('data-content', newData.content || '');

    insertRelatedNewsLinkByTime(newsListDiv, similarNewsItem);
    sortRelatedNewsLinksAscending(newsListDiv);

    const parentNewsItem = parentNewsContent.closest('.recent-news-item');
    if (parentNewsItem) {
        normalizeGroupedNewsItem(parentNewsItem);
    }
}

const RECENT_NEWS_DEDUP_WINDOW_MS = 3 * 60 * 1000;
const recentHandledNews = new Map();

function buildNewsDedupKey(news) {
    if (news && news.aid) {
        return `aid:${news.aid}`;
    }

    return [
        news?.categoryId || '',
        news?.comefrom || '',
        stripHtmlTags(news?.title || ''),
        stripHtmlTags(news?.content || '')
    ].join('|');
}

function pruneRecentHandledNews() {
    const now = Date.now();
    recentHandledNews.forEach((handledAt, key) => {
        if (now - handledAt > RECENT_NEWS_DEDUP_WINDOW_MS) {
            recentHandledNews.delete(key);
        }
    });
}

function hasRecentlyHandledNews(news) {
    pruneRecentHandledNews();
    const key = buildNewsDedupKey(news);
    if (!key) {
        return false;
    }

    const handledAt = recentHandledNews.get(key);
    return typeof handledAt === 'number' && (Date.now() - handledAt) <= RECENT_NEWS_DEDUP_WINDOW_MS;
}

function markNewsAsHandled(news) {
    const key = buildNewsDedupKey(news);
    if (!key) {
        return;
    }

    recentHandledNews.set(key, Date.now());
}

function hasRenderedNewsAid(aid) {
    if (!aid) {
        return false;
    }

    const normalizedAid = String(aid);
    return !!document.querySelector(`#news-list [data-aid="${normalizedAid}"]`)
        || pendingTopNewsItems.some(entry => entry.aid === normalizedAid);
}

function getNewsParentId(news) {
    if (!news || news.parent === undefined || news.parent === null) {
        return '';
    }

    const parentId = String(news.parent).trim();
    return parentId && parentId !== '0' ? parentId : '';
}

function runWithChildGroupingGuard(news, runFn) {
    if (typeof runFn !== 'function') {
        return;
    }

    if (!getNewsParentId(news)) {
        runFn();
    }
}

function runVoiceWithChildGroupingGuard(news, speakFn) {
    runWithChildGroupingGuard(news, speakFn);
}

function runPopupWithChildGroupingGuard(news, popupFn) {
    runWithChildGroupingGuard(news, popupFn);
}

function createWebSocket() {
    const socket = new WebSocket(buildWebSocketUrl());
    // 当连接打开时
    socket.onopen = function () {
        reconnectAttempts = 0;
        if (reconnectTimer) {
            clearTimeout(reconnectTimer);
            reconnectTimer = null;
        }
        console.log(`%c
                              _                       
               __ _ _   _ ___| |__   __ _ _ __   __ _ 
              / _\` | | | |_  / '_ \\ / _\` | '_ \\ / _\` |
             | (_| | |_| |/ /| | | | (_| | | | | (_| |
              \\__, |\\__,_/___|_| |_|\\__,_|_| |_|\\__, |
              |___/                             |___/ 
            
                已成功连接socket, Welcome to Guzhang!
            `, "color: rgb(255, 104, 98); font-weight: bold;"
        );
        // 开启心跳
        //startHeartbeat();
    };

    // 接收后端推送的数据
    socket.onmessage = function (event) {
        if(event.data == 'ping'){
            socket.send('pong');
            return;
        }
        let newData;
        try {
            newData = JSON.parse(event.data);
        } catch (e) {
            //console.error('WS data parse error:', event.data);
            return;
        }
        const t = String(newData.type || '').toLowerCase();
        if (t === 'ai_push' || t === 'aipush' || t === 'aipush' || t === 'aipush' || t === 'aipush') {
            return;
        }
        const currentCategorySetting = getCategorySettings();
        const categoryCid = Number(newData.categoryId);
        if (
            newData.categoryId &&
            !isNaN(categoryCid) &&
            categoryCid !== 1
        ) {
            // 找到包含这个 categoryCid 的那条配置
            const categoryConfig = currentCategorySetting.find(item => item[categoryCid] !== undefined);
        
            // 如果存在且值是“关闭状态” → 过滤
            if (categoryConfig) {
                const v = categoryConfig[categoryCid];
                if (v === 0 || v === '0' || v === false || v === '' || v == null) {
                    //console.log('过滤新闻', categoryCid, newData);
                    return;
                }
            }
        }
        // 防护空字段
        newData.title = newData.title || '';
        newData.content = newData.content || '';
        newData.ptime = newData.ptime || new Date().toISOString();
        if (!newData.title && !newData.content) {
            //console.warn('WS empty news skipped:', newData);
            return;
        }
        // 验证是否已经存在具有相同 aid 的新闻项
        if (hasRenderedNewsAid(newData.aid) || hasRecentlyHandledNews(newData)) {
            return; // 跳过插入操作
        }
        if (newData.title == 'refresh' && newData.comefrom == '鼓掌网') {
            scheduleAutoReload('ws-refresh', {
                minDelay: 20000,
                maxDelay: 120000
            });
            return;
        }
        if (newData.title == 'delete' && newData.comefrom == '鼓掌网') {
            const deleteAid = String(newData.content || '');
            const newsItemsToDelete = document.querySelectorAll(`li[data-aid="${deleteAid}"]`);
            newsItemsToDelete.forEach(item => item.remove());

            for (let i = pendingTopNewsItems.length - 1; i >= 0; i--) {
                if (pendingTopNewsItems[i].aid === deleteAid) {
                    pendingTopNewsItems.splice(i, 1);
                }
            }
            updatePendingTopNewsNotice();

            const relatedLinksToDelete = document.querySelectorAll(`.related-news a.news-item[data-aid="${deleteAid}"]`);
            relatedLinksToDelete.forEach(link => link.remove());

            normalizeAllGroupedNewsItems();
            reviveHiddenParents();
            sortNewsListItems();
            return;
        }
        if (
            settingsCookie &&
            settingsCookie['onlyShowKeywords'] == '1' &&
            settingsCookie['keywords'] &&
            typeof settingsCookie['keywords'] === 'string' &&
            settingsCookie['keywords'].trim() != '' &&
            newData.categoryId!=1
            
        ) {
            const keywords = settingsCookie['keywords']
                .split(',') // 假设关键词以逗号分隔
                .map(keyword => keyword.trim())
                .filter(keyword => keyword != ''); // 去除空关键词

            // 检查新闻标题或内容是否包含任意一个关键词
            const titleContainsKeyword = keywords.some(keyword =>
                newData.title.includes(keyword)
            );
            const contentContainsKeyword = keywords.some(keyword =>
                newData.content.includes(keyword)
            );

            if (!titleContainsKeyword && !contentContainsKeyword) {
                return; // 如果不包含任何关键词，跳过插入操作
            }
        }
        let shouldHide = false;
        if (newData.newConcept != 1) {
            // 查找 categorySetting 中是否存在与 newData.categoryId 对应的设置
            var category = currentCategorySetting.find(function(setting) {
                return setting[newData.categoryId] != undefined;
            });
            // 如果 categoryId 不在设置中，或其值不为 '1'，则返回
            if (!category || category[newData.categoryId] != '1') {
                // console.log(newData);
                shouldHide = true;
                
                //return; // 如果 categoryId 不在设置中或其值不为 '1'，则不执行后续操作
            }
        }
        if(newData.newConcept==1){
            markNewsAsHandled(newData);
            // 创建新的数据项元素
            const newItem = document.createElement('div');
            newItem.className = 'concept-item';
            newItem.setAttribute('data-id', newData.id);
            newItem.setAttribute('data-time', newData.time);
            newItem.style.backgroundColor = 'white';
            newItem.style.color = getColorByComefrom(newData.comefrom);
            newItem.innerHTML = `
                ${new Date(newData.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}
                <span style="font-weight:bold;margin-left:10px">${newData.name}(${newData.code})</span> 新增：<span style="font-weight:bold">${newData.concept}</span>
            `;
            const currentTime = Date.now();
            if (currentTime - lastSpeakTime < speakInterval || newData.comefrom!='同花顺') {
                // 如果距离上次播报的时间小于5秒，则不进行新的播报
                //console.log('忽略此次播报，间隔时间太短');
                //return;c
            }
            else{
                if(userPhone){
                    const userSettings = JSON.parse(settings);
                    if(userSettings.voiceConcept == 1){
                        speakNewsTitle(`${newData.name}新增：${newData.concept}概念`);
                    }
                }
                // else{
                //     if (!settingsCookie || settingsCookie.voiceConcept == 1) {
                //         speakNewsTitle(`${newData.name}新增：${newData.concept}概念`);
                //     }
                // }
            }
            lastSpeakTime = currentTime;
            // 获取 .layui-card-body 容器
            const container = document.querySelector('.layui-card-body');
            // 将新元素插入到容器内部的第一个位置
            const firstElement = container.firstChild;
            container.insertBefore(newItem, firstElement);
            return;
        }

        const parentId = getNewsParentId(newData);
        const parentNewsItem = parentId ? getCanonicalParentNewsContent(parentId) : null;
        if (parentId && parentNewsItem) {
            markNewsAsHandled(newData);
            if (settingsCookie && settingsCookie.hiddenRelated == '1') {
                reviveHiddenParents();
                return;
            }

            appendRelatedNewsToParent(parentNewsItem, newData);
        } else {
            markNewsAsHandled(newData);
            if(userPhone){
                const userSettings = JSON.parse(settings);
                // 将关键词和移除关键词转换为数组
                const keywords = userSettings.keywords ? userSettings.keywords.split(',') : [];
                const keywordsRemove = userSettings.keywordsRemove ? userSettings.keywordsRemove.split(',') : [];
                // 判断新闻是否包含需要的关键词
                function containsKeywords(content, keywords) {
                    return keywords.some(keyword => content.includes(keyword));
                }
                // 高亮关键词
                function highlightKeywords(content, keywords, keywordsRemove) {
                    // ✅ 避免 undefined/null 报错
                    if (content === undefined || content === null) {
                        content = '';
                    } else {
                        content = String(content);
                    }
                
                    // 如果需要高亮关键词
                    if (userSettings.highlightKeyword === "1" && Array.isArray(keywords)) {
                        keywords.forEach(keyword => {
                            if (!keyword) return; // 跳过空值
                            const regex = new RegExp(`(${keyword})`, 'gi');
                            content = content.replace(regex, '<span style="color:red;font-weight:bold">$1</span>');
                        });
                    }
                
                    // 如果有屏蔽词，将其标记为浅灰色
                    if (Array.isArray(keywordsRemove) && keywordsRemove.length > 0) {
                        content = safeReplace(content, keywordsRemove);
                    }

                
                    return content;
                }
                
                function safeReplace(content, keywordsRemove) {
                    // 创建 DOM 解析器
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(`<div>${content}</div>`, 'text/html');
                    const root = doc.body.firstChild;
                
                    // 遍历所有文本节点
                    function walk(node) { node.childNodes.forEach(child => { if (child.nodeType === 3) { highlightTextNode(child, keywordsRemove); } else { walk(child); } }); }
                
                    walk(root);
                
                    return root.innerHTML;
                }
                
                function highlightTextNode(node, keywordsRemove) {
                    let text = node.nodeValue;
                    let parent = node.parentNode;
                
                    // 创建一个文档片段（更高效）
                    let frag = document.createDocumentFragment();
                
                    let lastIndex = 0;
                
                    keywordsRemove.forEach(keyword => {
                        if (!keyword) return;
                
                        const regex = new RegExp(keyword, 'gi');
                        let match;
                
                        // 每次匹配都拆分文本节点
                        while ((match = regex.exec(text)) !== null) {
                            // 添加前面的普通文本
                            if (match.index > lastIndex) {
                                frag.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
                            }
                
                            // 添加高亮 span
                            const span = document.createElement('span');
                            span.style.color = '#d3d3d3';
                            span.textContent = match[0];
                            frag.appendChild(span);
                
                            lastIndex = match.index + match[0].length;
                        }
                    });
                
                    // 如果没有匹配，直接返回
                    if (lastIndex === 0) return;
                
                    // 添加剩余文本
                    if (lastIndex < text.length) {
                        frag.appendChild(document.createTextNode(text.slice(lastIndex)));
                    }
                
                    // 用 fragment 替换原文本节点
                    parent.replaceChild(frag, node);
                }


                function stripHTML(html) {
                    const div = document.createElement("div");
                    div.innerHTML = html;
                    return div.textContent || div.innerText || "";
                }
                
                function containsKeywords(content, keywords) {
                    if (!content || !keywords || keywords.length === 0) return false;
                
                    const text = stripHTML(content).toLowerCase();
                
                    return keywords.some(keyword =>
                        keyword && text.includes(keyword.toLowerCase())
                    );
                }
                
                function handleVoice(news, keywordsRemove, settingsCookie) {
                  // 过滤词拦截（保留你的逻辑）
                  if (
                    (containsKeywords(news.title, keywordsRemove) ||
                      containsKeywords(news.content, keywordsRemove)) &&
                    news.categoryId != 1
                  ) {
                    return;
                  }
                
                  // ✅ 登录用户：只看 userSettings（不要被 settingsCookie 影响）
                  if (userPhone) {
                    if (userSettings.voice == "1") {
                      if (userSettings.voiceKeyword == "1") {
                        if (
                          containsKeywords(news.title, keywords) ||
                          containsKeywords(news.content, keywords)
                        ) {
                          runVoiceWithChildGroupingGuard(news, function () {
                              speakNewsTitle(news.title, "", news.categoryId);
                          });
                        }
                      } else {
                        runVoiceWithChildGroupingGuard(news, function () {
                            speakNewsTitle(news.title, "", news.categoryId);
                        });
                      }
                    }
                    return;
                  }
                
                  // ✅ 游客：才使用 settingsCookie
                  const voiceOn =
                    settingsCookie && (settingsCookie.voice === 0 || settingsCookie.voice === "0")
                      ? false
                      : true; // 缺省 = true
                
                  if (voiceOn) {
                    runVoiceWithChildGroupingGuard(news, function () {
                        speakNewsTitle(news.title, "", news.categoryId);
                    });
                  }
                }

                // 处理弹窗通知逻辑
                function handlePopup(news,keywordsRemove) {
                    // 检查 news.title 或 news.content 中是否包含要移除的关键词
                    if (containsKeywords(news.title, keywordsRemove) || containsKeywords(news.content, keywordsRemove) && news.categoryId!=1) {
                        // 如果包含关键词，不执行弹窗推送
                        return;
                    }
                
                    if (userSettings.popup == "1") {
                        if (userSettings.popupKeyword == "1") {
                            if (containsKeywords(news.title, keywords) || containsKeywords(news.content, keywords)) {
                                runPopupWithChildGroupingGuard(news, function () {
                                    showNotification(news.title, news.content,news.categoryId);
                                });
                            }
                        } else {
                            runPopupWithChildGroupingGuard(news, function () {
                                showNotification(news.title, news.content,news.categoryId);
                            });
                        }
                    }
                }
                handleVoice(newData,keywordsRemove,settingsCookie);
                handlePopup(newData,keywordsRemove);
                // 高亮新闻标题和内容中的关键词
                newData.title = highlightKeywords(newData.title, keywords,keywordsRemove);
                newData.content = highlightKeywords(newData.content, keywords,keywordsRemove);

            }else{
                settingsCookie = getCookie('settingsCookie');
                if (settingsCookie) {
                    try {
                        settingsCookie = JSON.parse(settingsCookie);
                    } catch (e) {
                        settingsCookie = {};
                    }
                } else {
                    settingsCookie = {};
                }

                const voiceOn = (settingsCookie && (settingsCookie.voice === 0 || settingsCookie.voice === '0'))
                  ? false
                  : true; // 缺省 = true
                
                if (voiceOn) {
                    runVoiceWithChildGroupingGuard(newData, function () {
                        speakNewsTitle(newData.title,'',newData.categoryId);
                    });
                }
                
                if (Notification.permission == "granted" && (!settingsCookie || settingsCookie.popup == 1)) {
                    runPopupWithChildGroupingGuard(newData, function () {
                        showNotification(newData.title, newData.content,newData.categoryId);
                    });
                }
            }
            var comefroms = '';
            if(newData.comefrom=='鼓掌网'){
                comefroms = `
                    <div class="flex1">
                        
                    </div>`;
            }else{
                comefroms = `
                    <div class="flex1">
                        <span class="from">${newData.comefrom}</span>
                    </div>`;
            }
            // 创建新的新闻列表项
            const newNewsItem = document.createElement('li');
            
            newNewsItem.className = 'recent-news-item flexbox';
            if(newData.isPinned){
                newNewsItem.classList.add('pinned-news');
            }
            newNewsItem.setAttribute('data-aid', newData.aid);
            if (parentId) {
                newNewsItem.setAttribute('data-orphan-parent', parentId);
                newNewsItem.style.display = 'none';
            }
            if (shouldHide) {
                newNewsItem.style.display = 'none';
            }
            newNewsItem.setAttribute('data-category-id', newData.categoryId);
            newNewsItem.innerHTML = `
                <span class='ptime' style="display:none">${(new Date(newData.ptime).getTime())/1000}</span>
                <span class="time">${new Date(newData.ptime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}</span>
                <span class="time-line-point"></span>
                <div class="flex1 news-content">
                    <h2 class="word-ellipsis3">${newData.title}</h2>
                    <p>${newData.content}</p>
                    ${newData.stocks && newData.stocks.length > 0 ? `
                        <div class="stocks">
                            ${newData.stocks.map(stock => `
                                ${stock.name && stock.code.indexOf('HK') === -1 ? `
                                    <a class="mgt-block stocksDetails" href="http://s.guzhang.com:88/search?keywords=${stock.name}&keepAll=y&page=1&type=%E6%96%B0%E9%97%BB&sort=desc" code="${stock.code}" target="_blank">
                                        ${stock.name}
                                        <b class="${stock.rise < 0 ? 'stock-green' : 'stock-red'}">
                                            ${stock.rise >= 0 ? '+' : ''}${stock.rise}%
                                        </b>
                                    </a>
                                ` : ''}
                            `).join('')}
                        </div>
                    ` : ''}
                    <div class="flexbox" style="margin-top: 10px;">
                        ${comefroms}
                        <div>
                            <a class="clipboard-btn" data-clipboard-text="${getClipboardAttributeValue(newData.content)}" onclick="copyToClipboard(this)">
                                <span role="img" aria-label="share-alt" class="anticon anticon-share-alt" style="margin-right: 5px;">
                                    <svg viewBox="64 64 896 896" focusable="false" data-icon="copy" width="1em" height="1em" fill="currentColor" aria-hidden="true">
                                        <path d="M832 64H384c-35.2 0-64 28.8-64 64v192h64V128h448v576H576v64h256c35.2 0 64-28.8 64-64V128c0-35.2-28.8-64-64-64zm-192 192H192c-35.2 0-64 28.8-64 64v512c0 35.2 28.8 64 64 64h448c35.2 0 64-28.8 64-64V320c0-35.2-28.8-64-64-64zm0 576H192V320h448v512z"></path>
                                    </svg>
                                </span>
                                复制
                            </a>
                        </div>
                    </div>
                    ${newData.child && newData.child.length > 0 ? generateRelatedNewsHTML(newData.child, newData.aid) : ''}
                </div>
            `;
            if (!isNearNewsListTop()) {
                enqueuePendingTopNewsItem(newNewsItem, newData.isPinned);
                return;
            }

            insertTopNewsItem(newNewsItem, newData.isPinned);
            sortNewsListItems();
        }
        reviveHiddenParents();
    };

    // 当连接关闭时
    socket.onclose = function () {
        console.log('WebSocket connection closed');
        attemptReconnect();
    };

    // 处理错误
    socket.onerror = function (error) {
        console.error('WebSocket error: ', error);
    };

    return socket;
}
// 重连机制
let socket = createWebSocket();
// 紧急止血：暂停页面初始化时的最新新闻对齐请求，避免启动即打 POST /index
// syncLatestNews();

//let heartbeatInterval;
// function startHeartbeat() {
//     clearInterval(heartbeatInterval);  // 确保没有重复的定时器
//     heartbeatInterval = setInterval(() => {
//         if (socket.readyState === WebSocket.OPEN) {
//             socket.send('ping');  // 发送心跳包
//         }
//     }, 30000);  // 每30秒发送一次心跳包
// }
var reconnectAttempts = 0;  // 当前小时内的重连次数
const maxReconnectAttempts = 5;  // 每小时最大重连次数
let lastReconnectTime = Date.now();  // 上次重连的时间

function attemptReconnect() {
    const currentTime = Date.now();
    
    // 检查每小时是否已达到最大重连次数
    if (currentTime - lastReconnectTime >= 3600000) {
        // 每小时重置一次计数器
        reconnectAttempts = 0;
        lastReconnectTime = currentTime;
    }

    if (reconnectAttempts < maxReconnectAttempts) {
        if (reconnectTimer) {
            return;
        }
        reconnectAttempts++;
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            console.log('Attempting to reconnect WebSocket...');
            socket = createWebSocket();
            // 紧急止血：暂停重连成功后的最新新闻对齐请求，避免重连潮继续打 POST /index
            // syncLatestNews();
        }, 10000); // 10秒后尝试重连
    } else {
        console.log('Maximum reconnection attempts reached for this hour. Please wait until the next hour.');
    }
}

// 每分钟检查一次 WebSocket 连接状态
setInterval(() => {
    if (!socket || socket.readyState != WebSocket.OPEN) {
        console.log('WebSocket is not open, attempting to reconnect...');
        attemptReconnect();
        return;
    }
    // 紧急止血：暂停每 30 秒一次的最新新闻对齐请求，避免持续给服务器施压
    // syncLatestNews();
}, 30000);
let isLoading = false;
// 监听窗口的滚动事件
window.addEventListener('scroll', function () {
    flushPendingTopNewsItemsIfNearTop();

    const newsList = document.getElementById('news-list');
    // 获取 <ul> 元素的底部相对于视口的距离
    const ulBottomPosition = newsList.getBoundingClientRect().bottom;
    // 获取视口的高度
    const viewportHeight = window.innerHeight;
    // 当 <ul> 的底部进入视口时触发加载更多
    if (ulBottomPosition <= viewportHeight+100) {
        if (!isLoading) {
            loadMoreData();
        }
    }
});

function loadMoreData() {
    if (isLoading) return; // 如果已经在加载中，直接返回，避免重复执行
    isLoading = true;
    // 获取新闻列表中的最后一个 li 元素
    const newsList = document.getElementById('news-list');
    const lastNewsItem = newsList.querySelector('li:last-child .ptime');

    // 获取最后一个 .ptime 元素的文本内容
    const stimeValue = lastNewsItem ? (lastNewsItem.textContent || lastNewsItem.innerText) : '';

    // 发送POST请求
    fetch('index', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ stime: stimeValue }) // 传递最后一条新闻的时间，方便服务端进行分页
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'ok' && data.data.length > 0) {
            if (
                settingsCookie &&
                settingsCookie['onlyShowKeywords'] == '1' &&
                settingsCookie['keywords'] &&
                typeof settingsCookie['keywords'] === 'string' &&
                settingsCookie['keywords'].trim() != '' 
            ) {
                 const keywordsArray = settingsCookie['keywords']
                    .split(',')
                    .map(keyword => keyword.trim())
                    .filter(keyword => keyword != '');
    
                // 过滤包含任意一个关键词的新闻项
                const filteredData = data.data.filter(news => {
                    // 假设每个新闻项包含 title 和 content 字段
                    if (news.categoryId === 1) {
                        return true;
                    }
                    const title = news.title || '';
                    const content = news.content || '';
                    const combinedText = `${title} ${content}`.toLowerCase();
    
                    return keywordsArray.some(keyword => 
                        combinedText.includes(keyword.toLowerCase())
                    );
                });
                appendNews(filteredData);
            }else{
                appendNews(data.data);
            }
            
        }
    })
    .finally(() => {
        isLoading = false;
    });
}
function appendNews(news) {
    const newsList = document.getElementById('news-list');
    const currentCategorySetting = getCategorySettings();
    news.forEach(item => {
        // 查找 categorySetting 中是否存在与 item.categoryId 对应的设置
        var category = currentCategorySetting.find(function(setting) {
            return setting[item.categoryId] != undefined;
        });
        // 如果 categoryId 不在设置中，或其值不为 '1'，则跳过这条新闻
        if (!category || category[item.categoryId] != '1') {
            return; // 跳过这条新闻
        }
        const parentId = getNewsParentId(item);
        const parentNewsContent = parentId ? getCanonicalParentNewsContent(parentId) : null;
        if (parentId && parentNewsContent) {
            appendRelatedNewsToParent(parentNewsContent, item);
            return;
        }
        // 创建新的新闻列表项
        const li = document.createElement('li');
        li.className = 'recent-news-item flexbox';
        li.setAttribute('data-aid', item.aid);
        li.setAttribute('data-category-id', item.categoryId);
        // 如果有 parent 属性，则隐藏
        if (parentId) {
            li.setAttribute('data-orphan-parent', parentId);
            li.style.display = 'none';
        }
        var comefroms = '';
        if(item.comefrom=='鼓掌网'){
            comefroms = `
                <div class="flex1">
                    
                </div>`;
        }else{
            comefroms = `
                <div class="flex1">
                    <span class="from">${item.comefrom}</span>
                </div>`;
        }
        li.innerHTML = `
            <span class='ptime' style="display:none">${item.ptime_show}</span>
            <span class="time">${item.time_show}</span>
            <span class="time-line-point"></span>
            <div class="flex1 news-content">
                <h2 class="word-ellipsis3">${item.title}</h2>
                <p>${item.content}</p>
                ${item.stocks && item.stocks.length > 0 ? generateStocksHTML(item.stocks) : ''}
                <div class="flexbox" style="margin-top: 10px;">
                    ${comefroms}
                    <div>
                        <a class="clipboard-btn" data-clipboard-text="${getClipboardAttributeValue(item.content)}" onclick="copyToClipboard(this)">
                            <span role="img" aria-label="share-alt" class="anticon anticon-share-alt" style="margin-right: 5px;">
                                <svg viewBox="64 64 896 896" focusable="false" data-icon="copy" width="1em" height="1em" fill="currentColor" aria-hidden="true">
                                    <path d="M832 64H384c-35.2 0-64 28.8-64 64v192h64V128h448v576H576v64h256c35.2 0 64-28.8 64-64V128c0-35.2-28.8-64-64-64zm-192 192H192c-35.2 0-64 28.8-64 64v512c0 35.2 28.8 64 64 64h448c35.2 0 64-28.8 64-64V320c0-35.2-28.8-64-64-64zm0 576H192V320h448v512z"></path>
                                </svg>
                            </span>
                            复制
                        </a>
                    </div>
                </div>
                ${item.child && item.child.length > 0 ? generateRelatedNewsHTML(item.child, item.aid) : ''}
            </div>
        `;
        // 将新的新闻列表项追加到新闻列表中
        newsList.appendChild(li);
        normalizeGroupedNewsItem(li);
        reviveHiddenParents();
    });
}
function generateStocksHTML(stocks) {
    return `
        <div class="stocks">
            ${stocks.map(stock => `
                ${stock.name && stock.code.indexOf('HK') === -1 ? `
                    <a class="mgt-block stocksDetails" href="http://s.guzhang.com:88/search?keywords=${stock.name}&keepAll=y&page=1&type=%E6%96%B0%E9%97%BB&sort=desc" code="${stock.code}" target="_blank"> 
                        ${stock.name}
                        <b class="${stock.rise < 0 ? 'stock-green' : 'stock-red'}">
                            ${stock.rise >= 0 ? '+' : ''}${stock.rise}%
                        </b>
                    </a>
                ` : ''}
            `).join('')}
        </div>
    `;
}
function formatTimestampToTime(timeStrOrStamp) {
    let timestamp;

    // 判断是否是纯数字（时间戳秒数）
    if (/^\d+$/.test(timeStrOrStamp)) {
        timestamp = parseInt(timeStrOrStamp, 10);
    } else if (typeof timeStrOrStamp === 'string') {
        // 将日期字符串中的 '-' 替换为 '/'，兼容部分浏览器（如Safari）
        const safeTimeStr = timeStrOrStamp.replace(/-/g, '/');
        const date = new Date(safeTimeStr);
        if (isNaN(date.getTime())) {
            // 解析失败，返回空字符串
            return '';
        }
        timestamp = Math.floor(date.getTime() / 1000);
    } else {
        // 不是字符串也不是数字，返回空
        return '';
    }

    // 格式化为 24小时制时分秒
    const dateObj = new Date(timestamp * 1000);
    return dateObj.toLocaleTimeString('zh-CN', { hour12: false });
}

function legacyBrokenRelatedNewsHelper(children, parentAid = '') {
    return '';

    const normalizedParentAid = String(parentAid || '');
    const seenAids = new Set();
    const entries = [];

    childAids.forEach(childAid => {
        // 在页面中查找与 childAid 对应的新闻项
        const relatedNewsItem = document.querySelector(`#news-list li[data-aid="${childAid}"]`);
        if (relatedNewsItem) {
            const childTitle = relatedNewsItem.querySelector('h2')?.innerHTML;
            const childPtime = relatedNewsItem.querySelector('.ptime')?.textContent;
            const childComefrom = relatedNewsItem.querySelector('.from')?.textContent || '';

            if (childTitle) {  // 只有在 childTitle 不为空时才生成 HTML
                foundRelatedNews = true;
                const formattedTime = formatTimestampToTime(childPtime);
                relatedNewsHTML += `
                    <a class="news-item word-ellipsis"
                       href="javascript:void(0);"
                       data-aid="${childAid}"
                       data-category-id="${relatedNewsItem.getAttribute('data-category-id') || ''}"
                       data-ptime="${childPtime || ''}"
                       data-comefrom="${childComefrom || ''}"
                       data-title="${escapeHtml(childTitle || '')}"
                       data-content="${escapeHtml(relatedNewsItem.querySelector('.news-content p')?.innerHTML || '')}">
                        ${formattedTime}【${childComefrom}】${childTitle}
                    </a>
                `;
            }
        }
    });

    if (!foundRelatedNews) return ''; // 没有相关新闻则不显示模块
    
    return `
        <div class="related-news">
            <div class="title">相似文章</div>
            <div>${relatedNewsHTML}</div>
        </div>
    `;
}

function collectRelatedNewsEntries(children, parentAid = '') {
    const normalizedParentAid = String(parentAid || '');
    const seenAids = new Set();
    const entries = [];

    (Array.isArray(children) ? children : []).forEach(child => {
        let entry = null;

        if (child && typeof child === 'object' && !Array.isArray(child)) {
            entry = {
                aid: String(child.aid || ''),
                categoryId: String(child.categoryId || ''),
                ptime: child.ptime || child.ptime_show || child.ctime || '',
                comefrom: child.comefrom || '',
                title: child.title || '',
                content: child.content || ''
            };
        } else {
            const aid = String(child || '');
            if (!aid) {
                return;
            }

            const relatedNewsItem = document.querySelector(`#news-list li[data-aid="${aid}"]`);
            if (!relatedNewsItem) {
                return;
            }

            entry = {
                aid,
                categoryId: String(relatedNewsItem.getAttribute('data-category-id') || ''),
                ptime: relatedNewsItem.getAttribute('data-ptime') || relatedNewsItem.querySelector('.ptime')?.textContent || '',
                comefrom: relatedNewsItem.querySelector('.from')?.textContent || '',
                title: relatedNewsItem.querySelector('h2')?.innerHTML || '',
                content: relatedNewsItem.querySelector('.news-content p')?.innerHTML || ''
            };
        }

        if (!entry || !entry.aid || entry.aid === normalizedParentAid || seenAids.has(entry.aid)) {
            return;
        }

        seenAids.add(entry.aid);
        entries.push(entry);
    });

    return entries.sort((a, b) => parseNewsTimestamp(a.ptime) - parseNewsTimestamp(b.ptime));
}

function buildRelatedNewsLinkHtml(entry, parentId = '') {
    const parentAttr = parentId ? ` data-parent="${escapeHtml(parentId)}"` : '';
    return `
        <a class="news-item word-ellipsis"
           href="javascript:void(0);"
           data-aid="${escapeHtml(entry.aid || '')}"${parentAttr}
           data-category-id="${escapeHtml(entry.categoryId || '')}"
           data-ptime="${escapeHtml(entry.ptime || '')}"
           data-comefrom="${escapeHtml(entry.comefrom || '')}"
           data-title="${escapeHtml(entry.title || '')}"
           data-content="${escapeHtml(entry.content || '')}">
            ${formatRelatedNewsText(entry.ptime, entry.comefrom, entry.title)}
        </a>
    `;
}

function generateRelatedNewsHTML(children, parentAid = '') {
    const relatedEntries = collectRelatedNewsEntries(children, parentAid);
    if (relatedEntries.length === 0) {
        return '';
    }

    return `
        <div class="related-news">
            <div class="title">${RELATED_NEWS_TITLE}</div>
            <div class="related-news-list">${relatedEntries.map(entry => buildRelatedNewsLinkHtml(entry, parentAid)).join('')}</div>
        </div>
    `;
}

function formatTime(ptime) {
    if (!ptime) return '未知时间';
    const d = new Date(ptime);
    if (isNaN(d)) return '未知时间';
    return d.toLocaleTimeString('zh-CN', { hour12: false });
}

function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/[&<>"']/g, function(match) {
        return ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#39;'
        })[match];
    });
}
$(document).ready(function() {
    // 使用事件委托，将事件绑定到一个静态的父级元素上
    $(document).on('mouseenter', '.stocksDetails', function(event) {
        let originalCode = $(this).attr('code');
        let marketClass = getStockClass(originalCode);
        let fullCode = marketClass + originalCode;

        let imgUrl = 'https://imgnode.gtimg.cn/hq_img?type=minute&proj=financehome&code=' + fullCode;
        
        // 创建一个新的img元素
        let img = $('<img>').attr('src', imgUrl).css({
            'position': 'absolute',
            'top': event.pageY + 10 + 'px',  // 调整图片的位置
            'left': event.pageX + 10 + 'px', // 调整图片的位置
            'border': '1px solid #ccc',
            'background-color': '#fff',
            'padding': '5px',
            'z-index': 1000
        }).attr('id', 'stockChartImg');

        // 将img元素添加到body中
        $('body').append(img);
    });

    // 当鼠标移出.mgt-block元素时，移除图片
    $(document).on('mouseleave', '.stocksDetails', function() {
        $('#stockChartImg').remove();
    });

    // 更新图片位置
    $(document).on('mousemove', '.stocksDetails', function(event) {
        $('#stockChartImg').css({
            'top': event.pageY + 10 + 'px',
            'left': event.pageX + 10 + 'px'
        });
    });
    $('#toggleNewsSourceBtn').on('click', function() {
        $('#newsSourceWrapper').toggle(); // 切换显示或隐藏
        var isVisible = $('#newsSourceWrapper').is(':visible');
        $('#toggleText').text(isVisible ? '收起消息来源' : '显示消息来源');
    });

    // 绑定点击事件到所有 .ant-checkbox-input 类的复选框
    $('.ant-checkbox-input').on('click', function() {
        // 防止默认行为，阻止复选框自动选中/取消选中
        event.preventDefault();
        // 切换 checked 状态
        if ($(this).prop('checked')) {
            $(this).prop('checked', false);
        } else {
            $(this).prop('checked', false);
        }
        
        
    });


});
function getStockClass(code) {
    let code_symbol = code.substring(0, 2);
    let stockClass = '';

    switch (code_symbol) {
        case '60':
        case '68':
            stockClass = 'sh'; // 对应上交所
            break;
        case '30':
        case '00':
            stockClass = 'sz'; // 对应深交所
            break;
        default:
            code_symbol = code.charAt(0);
            if (code_symbol === '4' || code_symbol === '8') {
                stockClass = 'bj'; // 对应北京交易所
            }
    }
    return stockClass;
}
function copyToClipboard(element) {
    var newsItem = element.closest('.recent-news-item');
    var time = newsItem.querySelector('.time').innerText;
    var from = newsItem.querySelector('.from').innerText;
    var title = newsItem.querySelector('h2').innerText;
    title = stripHtmlTags(title);
    var content = element.getAttribute('data-clipboard-text');
    content = stripHtmlTags(content);
    var extraText = '-聚合724.guzhang.com';
    const textToCopy = content
      ? `${time}【${title}】\n${content}\n(${from}${extraText})`
      : `${time}【${title}】\n(${from}${extraText})`;

    
    
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(textToCopy).then(() => {
            showCopySuccessTip();
        }).catch(err => {
            console.error('复制失败:', err);
        });
    } else {
        // 兼容处理：如果浏览器不支持 navigator.clipboard
        const textArea = document.createElement("textarea");
        textArea.value = textToCopy;
        document.body.appendChild(textArea);
        textArea.select();
        try {
            document.execCommand('copy');
            showCopySuccessTip();
        } catch (err) {
            console.error('复制失败:', err);
        }
        document.body.removeChild(textArea);
    }
}

function showCopySuccessTip() {
    const tip = document.getElementById('copySuccessTip');
    tip.style.display = 'block';

    // 2秒后隐藏提示弹窗
    setTimeout(() => {
        tip.style.display = 'none';
    }, 2000);
}
document.getElementById('loadMoreConcept').addEventListener('click', function() {
    // 获取最后一个数据项的 data-id 和 data-time
    const items = document.querySelectorAll('.concept-item');
    const lastItem = items[items.length - 1];
    const lastId = lastItem ? lastItem.getAttribute('data-id') : null;
    const lastTime = lastItem ? lastItem.getAttribute('data-time') : null;
    // 准备发送的数据
    const requestData = {
        id: lastId,
        time: lastTime,
        type: 'concept'
    };

    // 发送POST请求
    fetch('index', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(requestData) // 传递最后一条新闻的ID和时间，以及类型
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'ok' && data.data.length > 0) {
            appendConcept(data.data); // 调用函数，将新数据追加到列表中
        }else{
            layer.msg('仅展示2天内的消息');
        }
    })
    .finally(() => {
        isLoading = false;
    });
});

// 函数：将新数据渲染到列表末尾
function appendConcept(newsItems) {
    const container = document.querySelector('.conceptsItem');
    //const loadMoreButton = document.getElementById('loadMoreConcept').parentNode;

    newsItems.forEach(item => {
        const newItem = document.createElement('div');
        newItem.className = 'concept-item';
        newItem.setAttribute('data-id', item.id);
        newItem.setAttribute('data-time', item.time);
        newItem.style.backgroundColor = 'white';
        newItem.style.color = getColorByComefrom(item.comefrom);

        // 解析 item.time 为日期对象
        const itemDate = new Date(item.time);
        const currentDate = new Date();

        let displayTime;
        if (
            itemDate.getDate() === currentDate.getDate() &&
            itemDate.getMonth() === currentDate.getMonth() &&
            itemDate.getFullYear() === currentDate.getFullYear()
        ) {
            // 如果是今天的新闻，显示 H:i:s 格式
            displayTime = itemDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
        } else {
            // 如果不是今天的新闻，显示 m-d H:i:s 格式
            const month = (itemDate.getMonth() + 1).toString().padStart(2, '0'); // 获取月份，确保两位
            const day = itemDate.getDate().toString().padStart(2, '0'); // 获取日期，确保两位
            displayTime = `${month}-${day} ${itemDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}`;
        }

        newItem.innerHTML = `
            ${displayTime}
            <span style="font-weight:bold;margin-left:10px">${item.name}(${item.code})</span> 新增：<span style="font-weight:bold">${item.concept}</span>
        `;
        container.appendChild(newItem);
    });
}




// 函数：根据 comefrom 字段获取相应的颜色
function getColorByComefrom(comefrom) {
    if (comefrom === '同花顺') {
        return 'rgba(255, 138, 132)';
    } else if (comefrom === '大智慧') {
        return 'rgba(70, 130, 180)';
    } else if (comefrom === '通达信') {
        return 'rgba(255, 165, 79)';
    } else {
        return '#000'; // 默认颜色
    }
}
function logout() {
    // 清除 Cookie
    document.cookie = "user_name=; expires=Thu, 01 Jan 1970 00:00:00 UTC;";
    document.cookie = "user_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC;";
    document.cookie = "settingsCookie=; expires=Thu, 01 Jan 1970 00:00:00 UTC;";
    
    // 显示弹窗
    alert('已退出登录');
    location.reload()
}
//设置部分
layui.use('layer', function() {
    var layer = layui.layer;
    $('#poperHandler').on('click', function() {
        // if (!isLoggedIn) {
        //     // 用户未登录，显示提示框
        //     layer.msg('您需要登录后才能使用此功能', {icon: 5, time: 2000}); // 提示信息，2秒后关闭
        // } else {
        //     // 用户已登录，弹出设置窗口
        //     $.get('../settings', {phone: userPhone}, function(data) {
        //         // 创建弹窗并将POST返回的数据载入iframe中
        //         layer.open({
        //             type: 1, // 使用type: 1，动态加载返回内容
        //             shadeClose: true, // 点击遮罩关闭弹窗
        //             title: false, // 去掉弹窗标题
        //             area: ['800px', '850px'], // 弹窗大小
        //             content: data // 将POST请求返回的内容作为弹窗内容
        //         });
        //     });
        // }
        $.get('../settings', {phone: userPhone}, function(data) {
            // 创建弹窗并将POST返回的数据载入iframe中
            layer.open({
                type: 1, // 使用type: 1，动态加载返回内容
                shadeClose: true, // 点击遮罩关闭弹窗
                title: false, // 去掉弹窗标题
                area: ['800px', '850px'], // 弹窗大小
                content: data // 将POST请求返回的内容作为弹窗内容
            });
        });
    });
});
function removeRedBoldSpans(inputString) {
    // 移除所有的 <span style="color:red;font-weight:bold"> 和 </span> 标签
    return inputString.replace(/<span style="color:red;font-weight:bold">|<\/span>/g, '');
}
function chineseText(input, speakLength = 30) {
    // 读取用户设置
    let userSetLength = null;
    if (settingsCookie && settingsCookie['speakLenght'] !== undefined) {
        userSetLength = Number(settingsCookie['speakLenght']);
    }

    // 兜底处理
    if (input === undefined || input === null) return '';

    // 转成字符串
    let text = String(input);

    // 移除 HTML 标签
    text = text.replace(/<\/?[^>]+>/g, '');

    // 移除红色加粗等自定义 span
    text = removeRedBoldSpans(text);

    // 移除不可见字符
    text = text.replace(/[\u200B-\u200F\u202A-\u202E]/g, '');

    // -----------------------------
    // 确定最终截取长度
    // -----------------------------
    let maxLength;
    if (userSetLength === null || isNaN(userSetLength)) {
        // 没有设置 → 默认 30
        maxLength = speakLength;
    } else if (userSetLength <= 0) {
        // 设置为 0 或负数 → 返回全部
        maxLength = 0;
    } else {
        // 设置为正数 → 按实际截取
        maxLength = userSetLength;
    }

    // 如果 maxLength = 0 → 返回完整文本
    if (maxLength === 0) {
        return text;
    }

    // -----------------------------
    // 按长度截取
    // -----------------------------
    const allowed = /[\u4e00-\u9fa5]|[a-zA-Z0-9]|[\u3000-\u303F\uFF00-\uFFEF]|[，,。.！!？?、；;：:‘’'"“”()（）【】《》%.\-+]/;

    let result = '';
    let count = 0;

    for (let char of text) {
        if (!allowed.test(char)) continue;

        let charCount = /[\u4e00-\u9fa5]/.test(char) ? 1 :
                        /[a-zA-Z0-9]/.test(char) ? 2 : 0;

        if (count + charCount > maxLength) break;

        result += char;
        count += charCount;
    }

    // 兜底：如果过滤后为空，至少返回前 maxLength 个字符
    if (result.trim() === '') {
        return text.slice(0, maxLength);
    }

    return result;
}







function speakNewsTitle(title, speed = 1.75, categoryId = 0) {
    // -----------------------------
    // 1. 栏目过滤逻辑（保持你的原逻辑）
    // -----------------------------
    if (categoryId != 0) {
        const cookieStr = getCookie('newsSourceSelections');
        const settings = cookieStr ? JSON.parse(decodeURIComponent(cookieStr)) : [];
        const catSetting = settings.find(item => item[categoryId] != undefined);
        if (!catSetting || catSetting[categoryId] != '1') {
            return; // 未开启栏目，不播报
        }
    }

    // -----------------------------
    // 2. 处理语速（避免字符串导致静默）
    // -----------------------------
    const cookieRate = getCookie('speakRate');
    if (cookieRate) {
        speed = Number(cookieRate) || speed;
    } else {
        const ua = navigator.userAgent;
        const isSafari = /^((?!chrome|android).)*safari/i.test(ua);

        if (isSafari) speed = 1.0;
        else if (/Windows/.test(ua)) speed = 1.75;
        else speed = 1.5;
    }

    // -----------------------------
    // 3. 处理中文文本
    // -----------------------------
    title = chineseText(title);
    // -----------------------------
    // 4. 核心稳定播报函数
    // -----------------------------
    function doSpeak() {
        const utter = new SpeechSynthesisUtterance(title);

        // Safari 必须指定中文，否则会静默
        utter.lang = "zh-CN";

        // rate 必须是数字
        utter.rate = Number(speed);

        // 避免 cancel() 吞播：必须延迟 speak()
        speechSynthesis.cancel();
        setTimeout(() => {
            speechSynthesis.speak(utter);
        }, 80); // 50–100ms 是最稳定的区间
    }

    // -----------------------------
    // 5. 确保 voices 已加载（Chrome/Safari 必须）
    // -----------------------------
    const voices = speechSynthesis.getVoices();
    if (voices.length === 0) {
        // 第一次加载 voices 时会触发
        speechSynthesis.onvoiceschanged = () => {
            doSpeak();
        };
    } else {
        doSpeak();
    }
}

function showNotification(title, content,categoryId=0) {
    
    if (categoryId != 0) {
        // 从 cookie 中读取栏目选择设置
        const cookieStr = getCookie('newsSourceSelections');
        
        const settings = cookieStr ? JSON.parse(decodeURIComponent(cookieStr)) : [];
        // 查找对应栏目的设置：1 表示选中
        const catSetting = settings.find(item => item[categoryId] != undefined);
        if (!catSetting || catSetting[categoryId] != '1') {
            // 若该栏目未开启，则不做播报
            return;
        }
    }
    
    
    if (title && Notification.permission != "granted") {
        layer.msg('您已禁止浏览器推送权限，如想开启请在浏览器设置。');
    }
    title = stripHtmlTags(title);
    content = stripHtmlTags(content);
    if (title != 0 || content != 0) {
        if (!("Notification" in window)) {
            alert("此浏览器不支持桌面通知");
        } else if (Notification.permission === "granted") {
            new Notification(title, { body: content });
        } else if (Notification.permission != "denied") {
            Notification.requestPermission().then(function (permission) {
                if (permission === "granted") {
                    new Notification(title, { body: content });
                }
            });
        }
    }
}
function stripHtmlTags(input) {
    const doc = new DOMParser().parseFromString(input, 'text/html');
    return doc.body.textContent || "";
}

function getClipboardAttributeValue(content) {
    return escapeHtml(stripHtmlTags(content || ''));
}

document.getElementById('captureBtn').addEventListener('click', function() {
    const targetElement = document.querySelector('.conceptsItem');

    // 创建水印图片元素并添加到 .conceptsItem 内
    const watermarkImg = document.createElement('img');
    watermarkImg.src = 'static/assets/waterprint.png';  // 水印图片路径
    watermarkImg.style.position = 'absolute';
    watermarkImg.style.top = '50%';
    watermarkImg.style.left = '50%';
    watermarkImg.style.transform = 'translate(-50%, -50%)';
    watermarkImg.style.opacity = '0.3';  // 设置水印透明度
    watermarkImg.style.pointerEvents = 'none';  // 防止水印干扰点击事件
    watermarkImg.style.width = '200px';  // 根据需要调整图片大小
    watermarkImg.style.height = 'auto';
    watermarkImg.classList.add('watermark');

    // 创建颜色说明元素并添加到 .conceptsItem 内
    const legendElement = document.createElement('div');
    legendElement.className = 'legend';
    legendElement.style.display = 'flex';
    legendElement.style.alignItems = 'center';
    legendElement.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
    legendElement.style.padding = '10px';
    legendElement.style.borderRadius = '8px';

    legendElement.innerHTML = `
        <h3 style="margin: 0; line-height: 1.5; font-weight:bold">新增概念</h3>
        <div style="margin-left:20px; display: flex; align-items: center; gap: 20px;">
            <div style="display: flex; align-items: center;">
                <span style="display: inline-block; width: 17px; height: 2px; background-color: rgba(255, 138, 132, 0.9); margin-right: 5px;"></span>
                <span style="font-size: 11px; color: #555;">同花顺</span>
            </div>
            <div style="display: flex; align-items: center;">
                <span style="display: inline-block; width: 17px; height: 2px; background-color: rgba(70, 130, 180, 0.9); margin-right: 5px;"></span>
                <span style="font-size: 11px; color: #555;">大智慧</span>
            </div>
            <div style="display: flex; align-items: center;">
                <span style="display: inline-block; width: 17px; height: 2px; background-color: rgba(255, 165, 79, 0.9); margin-right: 5px;"></span>
                <span style="font-size: 11px; color: #555;">通达信</span>
            </div>
        </div>

    `;

    // 将颜色说明添加到 .conceptsItem 元素的顶部
    targetElement.insertBefore(legendElement, targetElement.firstChild);
    targetElement.appendChild(watermarkImg);

    // 使用 html2canvas 对元素进行截图
    html2canvas(targetElement).then(function(canvas) {
        // 截图完成后移除水印和颜色说明元素
        targetElement.removeChild(watermarkImg);
        targetElement.removeChild(legendElement);

        // 将截图保存为图片
        const imageDataURL = canvas.toDataURL('image/png');
        const link = document.createElement('a');
        const now = new Date();
        const formattedDate = now.getFullYear() +
            ('0' + (now.getMonth() + 1)).slice(-2) +
            ('0' + now.getDate()).slice(-2) +
            ('0' + now.getHours()).slice(-2) +
            ('0' + now.getMinutes()).slice(-2) +
            ('0' + now.getSeconds()).slice(-2);
        link.download = `新增概念截图_${formattedDate}.png`;  // 设置下载文件名
        link.href = imageDataURL;
        link.click();  // 触发下载
    });
});
document.querySelector('.icon-wrapper').addEventListener('click', function() {
    document.querySelector('.browser-notice').style.display = 'none';
});
// 初始化时检查cookie
function initializeCheckboxes() {
    var cookieName = 'newsSourceSelections';
    var cookieValue = getCookie(cookieName);
    var checkboxes = document.querySelectorAll('.news-source-checkbox');
    if (cookieValue && cookieValue.length > 0) {
        // 如果cookie存在，解析并应用
        var selections = JSON.parse(cookieValue);
        checkboxes.forEach(function(checkbox) {
            var checkboxId = checkbox.getAttribute('data-id');
            
            // 查找 cookieValue 中与该 checkboxId 匹配的对象，并获取状态
            var selection = selections.find(function(item) {
                return item[checkboxId] != undefined;
            });
            if (selection) {
                // 如果找到对应的状态，设置 checked 属性
                checkbox.checked = selection[checkboxId] === '1';
            }
        });
    } else {
        // 如果cookie不存在，默认勾选所有选项，并保存到cookie
        var defaultSelections = Array.from(checkboxes).map(function(checkbox) {
            var id = checkbox.getAttribute('data-id');
            return { [id]: id === '14' ? '0' : '1' };
        });
        setCookie(cookieName, JSON.stringify(defaultSelections), NEWS_SOURCE_COOKIE_DAYS);
    }
}

// 设置cookie函数
function setCookie(name, value, days) {
    var expires = "";
    if (days) {
        var date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "") + expires + "; path=/";
}

//保存cookie并刷新页面
function handleCheckboxChange() {
    var checkboxes = document.querySelectorAll('.news-source-checkbox');
    var selections = Array.from(checkboxes).map(function(checkbox) {
        var checkboxId = checkbox.getAttribute('data-id');
        // 根据复选框是否选中保存状态，1为选中，0为未选中
        return { [checkboxId]: checkbox.checked ? '1' : '0' };
    });

    // 将更新后的 selections 保存到 cookie，并保存7天
    setCookie('newsSourceSelections', JSON.stringify(selections), NEWS_SOURCE_COOKIE_DAYS);

    // 刷新页面应用更改
    location.reload();
}



// 全局存储“复活”的子新闻节点
const revivedNodes = new Map();

function getCategorySettings() {
    const cookieStr = getCookie('newsSourceSelections');
    return cookieStr ? JSON.parse(cookieStr) : [];
}

function isCategoryEnabled(catId, settings) {
    const match = settings.find(item => item[catId] != undefined);
    return match ? match[catId] === '1' : true;
}

function getNewsTimestampFromElement(item) {
    if (!item) {
        return Math.floor(Date.now() / 1000);
    }

    const ptimeNode = item.querySelector('.ptime');
    if (ptimeNode) {
        const timestamp = parseNewsTimestamp(ptimeNode.textContent || '');
        if (timestamp > 0) {
            return timestamp;
        }
    }

    const rawTime = item.getAttribute('data-ptime') || '';
    if (rawTime) {
        const timestamp = parseNewsTimestamp(rawTime);
        if (timestamp > 0) {
            return timestamp;
        }
    }

    return Math.floor(Date.now() / 1000);
}

function buildOrphanRelatedLinkMarkup(item, parentId) {
    return buildRelatedNewsLinkHtml({
        aid: item.getAttribute('data-aid') || '',
        categoryId: item.getAttribute('data-category-id') || '',
        ptime: item.getAttribute('data-ptime') || String(getNewsTimestampFromElement(item)),
        comefrom: item.querySelector('.from')?.textContent || '',
        title: item.querySelector('h2')?.innerHTML || '',
        content: item.querySelector('.news-content p')?.innerHTML || ''
    }, parentId);
}

function extractNewsEntryFromItem(item) {
    if (!item) {
        return null;
    }

    const rawTime = item.getAttribute('data-ptime') || item.querySelector('.ptime')?.textContent || '';
    const timestamp = parseNewsTimestamp(rawTime) || getNewsTimestampFromElement(item);

    return {
        aid: String(item.getAttribute('data-aid') || ''),
        categoryId: String(item.getAttribute('data-category-id') || ''),
        ptime: rawTime || String(timestamp),
        timestamp,
        comefrom: item.querySelector('.from')?.textContent || '',
        title: item.querySelector('h2')?.innerHTML || '',
        content: item.querySelector('.news-content p')?.innerHTML || '',
        stocksHtml: item.querySelector('.stocks')?.outerHTML || ''
    };
}

function extractNewsEntryFromRelatedLink(link) {
    if (!link) {
        return null;
    }

    const aid = String(link.getAttribute('data-aid') || '');
    const sourceItem = aid ? document.querySelector(`#news-list li[data-aid="${aid}"]`) : null;
    if (sourceItem) {
        const sourceEntry = extractNewsEntryFromItem(sourceItem);
        if (sourceEntry) {
            sourceEntry.ptime = sourceEntry.ptime || link.getAttribute('data-ptime') || '';
            sourceEntry.timestamp = sourceEntry.timestamp || parseNewsTimestamp(sourceEntry.ptime);
            sourceEntry.comefrom = sourceEntry.comefrom || link.getAttribute('data-comefrom') || '';
            sourceEntry.title = sourceEntry.title || link.getAttribute('data-title') || '';
            sourceEntry.content = sourceEntry.content || link.getAttribute('data-content') || '';
            return sourceEntry;
        }
    }

    const rawTime = link.getAttribute('data-ptime') || '';
    return {
        aid,
        categoryId: String(link.getAttribute('data-category-id') || ''),
        ptime: rawTime,
        timestamp: parseNewsTimestamp(rawTime),
        comefrom: link.getAttribute('data-comefrom') || '',
        title: link.getAttribute('data-title') || '',
        content: link.getAttribute('data-content') || '',
        stocksHtml: ''
    };
}

function applyNewsEntryToItem(item, entry) {
    if (!item || !entry) {
        return;
    }

    const resolvedTimestamp = entry.timestamp || parseNewsTimestamp(entry.ptime);
    item.setAttribute('data-aid', entry.aid || item.getAttribute('data-aid') || '');
    item.setAttribute('data-category-id', entry.categoryId || item.getAttribute('data-category-id') || '');
    item.setAttribute('data-ptime', entry.ptime || String(resolvedTimestamp || ''));

    const ptimeNode = item.querySelector('.ptime');
    if (ptimeNode && resolvedTimestamp > 0) {
        ptimeNode.textContent = String(resolvedTimestamp);
    }

    const timeNode = item.querySelector('.time');
    if (timeNode) {
        timeNode.textContent = formatTimestampToTime(entry.ptime || String(resolvedTimestamp || ''));
    }

    const titleNode = item.querySelector('h2');
    if (titleNode) {
        titleNode.innerHTML = entry.title || '';
    }

    const newsContent = item.querySelector('.news-content');
    const contentNode = newsContent?.querySelector('p');
    if (contentNode) {
        contentNode.innerHTML = entry.content || '';
    }

    if (newsContent && contentNode) {
        const existingStocks = newsContent.querySelector('.stocks');
        if (existingStocks) {
            existingStocks.remove();
        }
        if (entry.stocksHtml) {
            contentNode.insertAdjacentHTML('afterend', entry.stocksHtml);
        }
    }

    const sourceContainer = item.querySelector('.news-content .flexbox .flex1');
    if (sourceContainer) {
        let fromNode = sourceContainer.querySelector('.from');
        if (entry.comefrom && entry.comefrom !== '鼓掌网') {
            if (!fromNode) {
                fromNode = document.createElement('span');
                fromNode.className = 'from';
                sourceContainer.appendChild(fromNode);
            }
            fromNode.textContent = entry.comefrom;
        } else if (fromNode) {
            fromNode.remove();
        }
    }

    const copyBtn = item.querySelector('.clipboard-btn');
    if (copyBtn) {
        copyBtn.setAttribute('data-clipboard-text', stripHtmlTags(entry.content || ''));
    }
}

function renderRelatedEntriesForItem(item, childEntries) {
    const newsContent = item.querySelector('.news-content');
    if (!newsContent) {
        return;
    }

    const parentRefId = item.getAttribute('data-orphan-parent') || item.getAttribute('data-aid') || '';
    let relatedNewsDiv = newsContent.querySelector('.related-news');

    if (!childEntries || childEntries.length === 0) {
        if (relatedNewsDiv) {
            relatedNewsDiv.remove();
        }
        return;
    }

    if (!relatedNewsDiv) {
        relatedNewsDiv = document.createElement('div');
        relatedNewsDiv.className = 'related-news';
        newsContent.appendChild(relatedNewsDiv);
    }

    relatedNewsDiv.innerHTML = `
        <div class="title">${RELATED_NEWS_TITLE}</div>
        <div class="related-news-list">${childEntries.map(entry => buildRelatedNewsLinkHtml(entry, parentRefId)).join('')}</div>
    `;

    sortRelatedNewsLinksAscending(relatedNewsDiv.querySelector('.related-news-list'));
}

function normalizeGroupedNewsItem(item) {
    if (!item) {
        return;
    }

    const currentAid = String(item.getAttribute('data-aid') || '');
    const relatedNewsDiv = item.querySelector('.related-news');
    if (!relatedNewsDiv) {
        return;
    }

    let relatedList = relatedNewsDiv.querySelector('.related-news-list');
    if (!relatedList) {
        const divChildren = Array.from(relatedNewsDiv.children).filter(function (child) {
            return child.tagName === 'DIV';
        });
        relatedList = divChildren[1] || null;
    }

    if (!relatedList) {
        return;
    }

    const seenAids = new Set();
    const orderedLinks = Array.from(relatedList.querySelectorAll('a.news-item'))
        .sort((a, b) => parseNewsTimestamp(a.getAttribute('data-ptime')) - parseNewsTimestamp(b.getAttribute('data-ptime')))
        .filter(link => {
            const aid = String(link.getAttribute('data-aid') || '');
            if (!aid || aid === currentAid || seenAids.has(aid)) {
                return false;
            }
            seenAids.add(aid);
            return true;
        });

    if (orderedLinks.length === 0) {
        relatedNewsDiv.remove();
        return;
    }

    orderedLinks.forEach(link => {
        link.innerHTML = formatRelatedNewsText(
            link.getAttribute('data-ptime') || '',
            link.getAttribute('data-comefrom') || '',
            link.getAttribute('data-title') || ''
        );
        relatedList.appendChild(link);
    });
}

function normalizeAllGroupedNewsItems() {
    document.querySelectorAll('#news-list .recent-news-item').forEach(item => {
        normalizeGroupedNewsItem(item);
    });
}

function updateTopNewsHighlight() {
    const newsList = document.getElementById('news-list');
    if (!newsList) {
        return;
    }

    const items = Array.from(newsList.children).filter(item => item.classList && item.classList.contains('recent-news-item'));
    items.forEach(item => item.classList.remove('important'));

    const firstVisibleItem = items.find(item => window.getComputedStyle(item).display !== 'none');
    if (firstVisibleItem) {
        firstVisibleItem.classList.add('important');
    }
}

function sortNewsListItems() {
    const newsList = document.getElementById('news-list');
    if (!newsList) {
        return;
    }

    const items = Array.from(newsList.children).filter(item => item.classList && item.classList.contains('recent-news-item'));
    items
        .sort((a, b) => {
            const aPinned = a.classList.contains('pinned-news');
            const bPinned = b.classList.contains('pinned-news');
            if (aPinned !== bPinned) {
                return aPinned ? -1 : 1;
            }

            return getNewsTimestampFromElement(b) - getNewsTimestampFromElement(a);
        })
        .forEach(item => {
            if (item.parentNode === newsList) {
                newsList.appendChild(item);
            }
        });

    updateTopNewsHighlight();
}

function insertRevivedNewsNode(newsList, node, timestamp) {
    const allItems = Array.from(newsList.querySelectorAll('.recent-news-item'));
    const insertBeforeItem = allItems.find(el => {
        return getNewsTimestampFromElement(el) < timestamp;
    });

    if (insertBeforeItem) {
        insertBeforeItem.before(node);
        return;
    }

    newsList.appendChild(node);
}

function reviveHiddenParents() {
    const categorySetting = getCategorySettings();
    const newsList = document.getElementById('news-list');
    if (!newsList) return;

    const newsItems = Array.from(newsList.querySelectorAll('.recent-news-item'));

    // 清理之前复活的节点
    revivedNodes.forEach(node => {
        if (node.parentNode) node.parentNode.removeChild(node);
    });
    revivedNodes.clear();

    newsItems.forEach(item => {
        const hiddenParentAid = item.getAttribute('data-aid');
        const orphanParentId = item.getAttribute('data-orphan-parent') || '';
        const catId = item.getAttribute('data-category-id');
        const isVisible = isCategoryEnabled(catId, categorySetting);

        if (orphanParentId) {
            item.style.display = 'none';
            return;
        }

        if (isVisible) {
            item.style.display = '';
            return;
        }

        item.style.display = 'none';

        if (getVisibleOrphanParentItem(hiddenParentAid)) {
            return;
        }

        const relatedNewsWrapper = item.querySelector('.related-news');
        if (!relatedNewsWrapper) return;

        const childLinks = relatedNewsWrapper.querySelectorAll('a.news-item');
        const eligibleChildren = Array.from(childLinks)
            .filter(link => {
                const cid = link.getAttribute('data-category-id');
                return cid && isCategoryEnabled(cid, categorySetting);
            })
            .sort((a, b) => parseNewsTimestamp(a.getAttribute('data-ptime')) - parseNewsTimestamp(b.getAttribute('data-ptime')));

        if (eligibleChildren.length === 0) return;

        const revived = eligibleChildren[0];
        const revivedAid = revived.getAttribute('data-aid');

        if (revivedNodes.has(revivedAid)) return;

        const revivedTitle = revived.getAttribute('data-title');
        const revivedTimeStr = revived.getAttribute('data-ptime') || '';
        const safeTimeStr = revivedTimeStr.replace(/-/g, '/');
        let revivedTimestamp = 0;
        const revivedDate = new Date(safeTimeStr);
        if (!isNaN(revivedDate.getTime())) {
            revivedTimestamp = Math.floor(revivedDate.getTime() / 1000);
        } else {
            revivedTimestamp = Math.floor(Date.now() / 1000);
        }
        const revivedComefrom = revived.getAttribute('data-comefrom') || '';
        const revivedContent = revived.getAttribute('data-content') || '';
        const revivedCategoryId = revived.getAttribute('data-category-id');

        const otherChildrenHTML = eligibleChildren
            .filter(link => link != revived)
            .map(link => buildRelatedNewsLinkHtml({
                aid: link.getAttribute('data-aid') || '',
                categoryId: link.getAttribute('data-category-id') || '',
                ptime: link.getAttribute('data-ptime') || '',
                comefrom: link.getAttribute('data-comefrom') || '',
                title: link.getAttribute('data-title') || '',
                content: link.getAttribute('data-content') || ''
            }, hiddenParentAid))
            .join('');

        const relatedNewsHTML = otherChildrenHTML
            ? `<div class="related-news">
                    <div class="title">${RELATED_NEWS_TITLE}</div>
                    <div class="related-news-list">${otherChildrenHTML}</div>
               </div>`
            : '';

        const newLi = document.createElement('li');
        newLi.className = 'recent-news-item flexbox revived-news-item';
        newLi.setAttribute('data-aid', revivedAid);
        newLi.setAttribute('data-orphan-parent', hiddenParentAid);
        newLi.setAttribute('data-category-id', revivedCategoryId);
        newLi.innerHTML = `
            <span class='ptime' style="display:none">${revivedTimestamp}</span>
            <span class="time">${new Date(revivedTimestamp * 1000).toLocaleTimeString('zh-CN', { hour12: false })}</span>
            <span class="time-line-point"></span>
            <div class="flex1 news-content">
                <h2 class="word-ellipsis3">${revivedTitle}</h2>
                <p>${revivedContent}</p>
                <div class="flexbox" style="margin-top: 10px;">
                    <div class="flex1">
                        ${revivedComefrom != '鼓掌网' ? `<span class="from">${revivedComefrom}</span>` : ''}
                    </div>
                    <div>
                        <a class="clipboard-btn" data-clipboard-text="${getClipboardAttributeValue(revivedContent)}" onclick="copyToClipboard(this)">
                            <span role="img" aria-label="share-alt" class="anticon anticon-share-alt" style="margin-right: 5px;">
                                <svg viewBox="64 64 896 896" focusable="false" data-icon="copy" width="1em" height="1em" fill="currentColor" aria-hidden="true">
                                    <path d="M832 64H384c-35.2 0-64 28.8-64 64v192h64V128h448v576H576v64h256c35.2 0 64-28.8 64-64V128c0-35.2-28.8-64-64-64zm-192 192H192c-35.2 0-64 28.8-64 64v512c0 35.2 28.8 64 64 64h448c35.2 0 64-28.8 64-64V320c0-35.2-28.8-64-64-64zm0 576H192V320h448v512z"></path>
                                </svg>
                            </span>
                            复制
                        </a>
                    </div>
                </div>
                ${relatedNewsHTML}
            </div>
        `;

        // 时间倒序插入
        insertRevivedNewsNode(newsList, newLi, revivedTimestamp);

        revivedNodes.set(revivedAid, newLi);
    });

    const orphanGroups = new Map();
    newsItems.forEach(item => {
        const parentId = item.getAttribute('data-orphan-parent') || '';
        if (!parentId) {
            return;
        }

        const catId = item.getAttribute('data-category-id');
        if (!isCategoryEnabled(catId, categorySetting)) {
            item.style.display = 'none';
            return;
        }

        item.style.display = 'none';

        if (getVisibleParentNewsItem(parentId)) {
            return;
        }

        if (!orphanGroups.has(parentId)) {
            orphanGroups.set(parentId, []);
        }
        orphanGroups.get(parentId).push(item);
    });

    orphanGroups.forEach((items, parentId) => {
        items.sort((a, b) => getNewsTimestampFromElement(a) - getNewsTimestampFromElement(b));
        const leader = items[0];
        if (!leader) {
            return;
        }

        const leaderAid = leader.getAttribute('data-aid');
        if (!leaderAid || revivedNodes.has(leaderAid)) {
            return;
        }

        const proxyNode = leader.cloneNode(true);
        proxyNode.classList.add('revived-news-item');
        proxyNode.style.display = '';
        proxyNode.setAttribute('data-orphan-parent', parentId);

        const siblingMarkup = items
            .slice(1)
            .map(item => buildOrphanRelatedLinkMarkup(item, parentId))
            .join('');

        if (siblingMarkup) {
            const newsContent = proxyNode.querySelector('.news-content');
            if (newsContent) {
                let relatedNewsDiv = newsContent.querySelector('.related-news');
                if (!relatedNewsDiv) {
                    relatedNewsDiv = document.createElement('div');
                    relatedNewsDiv.className = 'related-news';
                    relatedNewsDiv.innerHTML = `<div class="title">${RELATED_NEWS_TITLE}</div><div class="related-news-list"></div>`;
                    newsContent.appendChild(relatedNewsDiv);
                }

                let relatedList = relatedNewsDiv.querySelector('.related-news-list');
                if (!relatedList) {
                    relatedList = document.createElement('div');
                    relatedList.className = 'related-news-list';
                    relatedNewsDiv.appendChild(relatedList);
                }

                relatedList.innerHTML = siblingMarkup;
            }
        }

        insertRevivedNewsNode(newsList, proxyNode, getNewsTimestampFromElement(leader));
        revivedNodes.set(leaderAid, proxyNode);
    });

    normalizeAllGroupedNewsItems();
    sortNewsListItems();
}





// 页面加载时初始化复选框
document.addEventListener('DOMContentLoaded', function () {
    const checkboxes = document.querySelectorAll('.news-source-checkbox');

    checkboxes.forEach(cb => {
        cb.addEventListener('change', function () {
            updateCategoryCookie();
            refreshNewsDisplay();
        });
    });

    refreshNewsDisplay();

    function updateCategoryCookie() {
        const selections = [];
        checkboxes.forEach(cb => {
            const id = cb.getAttribute('data-id');
            const checked = cb.checked ? '1' : '0';
            const obj = {};
            obj[id] = checked;
            selections.push(obj);
        });
        setCookie('newsSourceSelections', JSON.stringify(selections), NEWS_SOURCE_COOKIE_DAYS);
        categorySetting = selections;
    }

    function getCategorySettings() {
        const cookieStr = getCookie('newsSourceSelections');
        return cookieStr ? JSON.parse(cookieStr) : [];
    }

    function isCategoryEnabled(catId, settings) {
        const match = settings.find(item => item[catId] != undefined);
        return match ? match[catId] === '1' : true;
    }

    function refreshNewsDisplay() {
        const categorySetting = getCategorySettings();
        const newsItems = Array.from(document.querySelectorAll('.recent-news-item'));

        // 清理之前复活的节点

        newsItems.forEach(item => {
            const catId = item.getAttribute('data-category-id');
            const orphanParentId = item.getAttribute('data-orphan-parent') || '';
            const shouldShow = isCategoryEnabled(catId, categorySetting) && !orphanParentId;

            item.style.display = shouldShow ? '' : 'none';


            // 复活第一个子新闻作为独立新闻显示
        });
        reviveHiddenParents();
    }
});







// const checkbox = document.getElementById('jinshi');
// checkbox.addEventListener('click', function(e) {
//     if(this.checked){
//         if (!confirm('温馨提示：您当前选择的栏目新闻较多，可能会造成频繁刷屏或语音提示，是否继续勾选？')) {
//             e.preventDefault(); // 阻止选中
//         }
//     }
// });
