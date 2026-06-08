import { db } from "./firebase-config.js";

import {
  doc,
  getDoc,
  collection,
  getDocs,
  query,
  orderBy,
  limit
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const ETF_CODE = "0048K0";

let priceChart = null;
let currentChartMode = "daily";

function formatNumber(value) {
  if (value === null || value === undefined || isNaN(value)) return "-";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function getChangeClass(value) {
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}

function getStockCodeFromUrl() {
  const params = new URLSearchParams(location.search);
  return params.get("code") || ETF_CODE;
}

async function loadStockDetail(code) {
  const stockRef = doc(db, "stocks", code);
  const stockSnap = await getDoc(stockRef);

  if (!stockSnap.exists()) {
    document.getElementById("detailName").innerText = "종목을 찾을 수 없습니다.";
    return null;
  }

  const stock = stockSnap.data();

  const current = Number(stock.current || 0);
  const previous = Number(stock.previous || 0);
  const diff = current - previous;
  const rate = previous === 0 ? 0 : diff / previous;
  const cls = getChangeClass(diff);

  document.getElementById("detailCode").innerText = stock.code || code;
  document.getElementById("detailName").innerText = stock.name || "종목 상세";
  document.getElementById("current").innerText = formatNumber(current);
  document.getElementById("previous").innerText = formatNumber(previous);

  const rateEl = document.getElementById("changeRate");
  rateEl.innerText = `${rate > 0 ? "+" : ""}${(rate * 100).toFixed(2)}%`;
  rateEl.className = cls;

  document.getElementById("volume").innerText = formatNumber(stock.volume);

  document.getElementById("detailTime").innerText =
    new Date().toLocaleString();

  return stock;
}

async function loadDailyHistory(code) {
  const historyRef = collection(db, "stocks", code, "historyDaily");

  const q = query(
    historyRef,
    orderBy("date", "asc"),
    limit(365)
  );

  const snapshot = await getDocs(q);

  const history = [];

  snapshot.forEach((docSnap) => {
    const data = docSnap.data();

    history.push({
      id: docSnap.id,
      label: data.date || docSnap.id,
      price: Number(data.close || data.current || 0),
      volume: Number(data.volume || 0),
      updatedAt: data.updatedAt || ""
    });
  });

  return history;
}

async function loadIntradayHistory(code) {
  const historyRef = collection(db, "stocks", code, "historyIntraday");

  const q = query(
    historyRef,
    orderBy("dateTime", "asc"),
    limit(300)
  );

  const snapshot = await getDocs(q);

  const today = new Date().toISOString().slice(0, 10);

  const history = [];

  snapshot.forEach((docSnap) => {
    const data = docSnap.data();

    if (data.date === today) {
      history.push({
        id: docSnap.id,
        label: data.time || data.dateTime || docSnap.id,
        price: Number(data.price || data.current || 0),
        volume: Number(data.volume || 0),
        updatedAt: data.dateTime || ""
      });
    }
  });

  return history;
}

function renderHistoryTable(history) {
  const tbody = document.getElementById("historyTable");

  if (!tbody) return;

  tbody.innerHTML = "";

  history
    .slice()
    .reverse()
    .forEach((row) => {
      tbody.innerHTML += `
        <tr>
          <td>${row.label}</td>
          <td>${formatNumber(row.price)}</td>
          <td>${formatNumber(row.volume)}</td>
        </tr>
      `;
    });
}

function renderPriceChart(history, mode) {
  const canvas =
    document.getElementById("priceChart") ||
    document.getElementById("closeChart");

  if (!canvas) return;

  if (priceChart) {
    priceChart.destroy();
    priceChart = null;
  }

  if (!history.length) {
    console.log("차트 표시용 history 데이터가 없습니다.");
    return;
  }

  const labels = history.map(row => row.label);
  const prices = history.map(row => Number(row.price));

  const high = Math.max(...prices);
  const low = Math.min(...prices);
  const isFlat = high === low;

  const yPadding = isFlat ? Math.max(1, high * 0.01) : 0;

  const titleText = mode === "daily"
    ? `일별 추이 - 최고 ${formatNumber(high)}원 / 최저 ${formatNumber(low)}원`
    : `당일 추이 - 최고 ${formatNumber(high)}원 / 최저 ${formatNumber(low)}원`;

  priceChart = new Chart(canvas, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: mode === "daily" ? "일별 종가" : "당일 현재가",
          data: prices,
          tension: isFlat ? 0 : 0.35,
          pointRadius: 3,
          pointHoverRadius: 5,
          fill: false
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: true
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              return `가격: ${formatNumber(context.raw)}원`;
            }
          }
        },
        title: {
          display: true,
          text: titleText
        }
      },
      scales: {
        y: {
          suggestedMin: isFlat ? low - yPadding : undefined,
          suggestedMax: isFlat ? high + yPadding : undefined,
          ticks: {
            callback: function (value) {
              return formatNumber(value);
            }
          }
        }
      }
    }
  });
}

async function showChart(mode) {
  const code = getStockCodeFromUrl();

  currentChartMode = mode;

  const dailyTab = document.getElementById("dailyTab");
  const intradayTab = document.getElementById("intradayTab");

  if (dailyTab && intradayTab) {
    if (mode === "daily") {
      dailyTab.classList.add("active");
      intradayTab.classList.remove("active");
    } else {
      dailyTab.classList.remove("active");
      intradayTab.classList.add("active");
    }
  }

  const history = mode === "daily"
    ? await loadDailyHistory(code)
    : await loadIntradayHistory(code);

  renderHistoryTable(history);
  renderPriceChart(history, mode);
}

window.showChart = showChart;

async function initDetailPage() {
  try {
    const code = getStockCodeFromUrl();

    await loadStockDetail(code);

    const dailyTab = document.getElementById("dailyTab");
    const intradayTab = document.getElementById("intradayTab");

    if (dailyTab) {
      dailyTab.addEventListener("click", () => showChart("daily"));
    }

    if (intradayTab) {
      intradayTab.addEventListener("click", () => showChart("intraday"));
    }

    await showChart(currentChartMode);

  } catch (error) {
    console.error("상세페이지 로딩 오류:", error);
    document.getElementById("detailName").innerText =
      "상세 데이터를 불러오지 못했습니다.";
  }
}

initDetailPage();
