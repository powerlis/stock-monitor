import { db } from "./firebase-config.js";

import {
  collection,
  getDocs,
  doc,
  getDoc,
  updateDoc
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

const ETF_CODE = "0048K0";
const ETF_NAVER_URL = "https://m.stock.naver.com/domestic/stock/0048K0/total";

let etfStock = null;
let componentStocks = [];
let portfolioChart = null;

function formatNumber(value) {
  if (value === null || value === undefined || isNaN(value)) return "-";

  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 2
  });
}

function formatPercent(value) {
  if (value === null || value === undefined || isNaN(value)) return "-";

  return (Number(value) * 100).toFixed(2) + "%";
}

function getChangeClass(value) {
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}

window.goDetail = function (code) {
  location.href = `detail.html?code=${encodeURIComponent(code)}`;
};

window.openNaver = function (url) {
  if (!url) return;

  window.open(url, "_blank", "noopener,noreferrer");
};

async function loadEtfFromFirestore() {
  const docRef = doc(db, "stocks", ETF_CODE);
  const docSnap = await getDoc(docRef);

  if (docSnap.exists()) {
    etfStock = docSnap.data();
  } else {
    etfStock = {
      type: "ETF",
      name: "KODEX 차이나휴머노이드로봇",
      code: ETF_CODE,
      naverUrl: ETF_NAVER_URL,
      current: 0,
      previous: 0,
      open: 0,
      high: 0,
      low: 0,
      volume: 0,
      market: "한국"
    };
  }

  if (!etfStock.naverUrl) {
    etfStock.naverUrl = ETF_NAVER_URL;
  }

  window.etfStock = etfStock;

  loadEtf();

  await renderAssetStatus();
}

async function loadComponentsFromFirestore() {
  const querySnapshot = await getDocs(collection(db, "stocks"));

  const stocks = [];

  querySnapshot.forEach((docSnap) => {
    const data = docSnap.data();

    if (data.type === "COMPONENT") {
      const current = Number(data.current || 0);
      const previous = Number(data.previous || 0);
      const diff = current - previous;
      const changeRate = previous === 0 ? 0 : diff / previous;

      stocks.push({
        id: docSnap.id,
        ...data,
        current,
        previous,
        diff,
        changeRate
      });
    }
  });

  stocks.sort((a, b) =>
    Number(a.rank || 999) - Number(b.rank || 999)
  );

  componentStocks = stocks;

  renderStocks();
  renderPortfolioChart();
}

async function getAssetAccounts() {
  const querySnapshot = await getDocs(collection(db, "accounts"));

  const accounts = [];

  querySnapshot.forEach((docSnap) => {
    accounts.push({
      id: docSnap.id,
      ...docSnap.data()
    });
  });

  accounts.sort((a, b) =>
    Number(a.order) - Number(b.order)
  );

  return accounts;
}

async function renderAssetStatus() {
  if (!etfStock) return;

  const accounts = await getAssetAccounts();
  const currentPrice = Number(etfStock.current);

  const profitTable =
    document.getElementById("assetProfitTable");

  const editTable =
    document.getElementById("assetEditTable");

  if (!profitTable || !editTable) return;

  profitTable.innerHTML = "";
  editTable.innerHTML = "";

  accounts.forEach((item) => {
    const quantity = Number(item.quantity);
    const avgPrice = Number(item.avgPrice);

    const profit =
      (currentPrice - avgPrice) * quantity;

    const profitRate =
      avgPrice === 0
        ? 0
        : ((currentPrice - avgPrice) / avgPrice) * 100;

    const profitClass =
      profit >= 0 ? "profit-plus" : "profit-minus";

    profitTable.innerHTML += `
      <tr>
        <td>${item.account}</td>
        <td class="${profitClass}">${profitRate >= 0 ? "+" : ""}${profitRate.toFixed(2)}%</td>
        <td class="${profitClass}">${profit >= 0 ? "+" : ""}${formatNumber(profit)}원</td>
        <td>${formatNumber(quantity)}</td>
        <td>${formatNumber(avgPrice)}원</td>
        <td>${formatNumber(currentPrice)}원</td>
      </tr>
    `;

    editTable.innerHTML += `
      <tr>
        <td>${item.account}</td>
        <td>
          <input type="number" id="qty-${item.id}" value="${quantity}">
        </td>
        <td>
          <input type="number" id="avg-${item.id}" value="${avgPrice}">
        </td>
      </tr>
    `;
  });
}

window.showAssetTab = function (tab) {
  const profitPanel =
    document.getElementById("profitPanel");

  const editPanel =
    document.getElementById("editPanel");

  const profitTab =
    document.getElementById("profitTab");

  const editTab =
    document.getElementById("editTab");

  if (tab === "profit") {
    profitPanel.classList.remove("hidden");
    editPanel.classList.add("hidden");
    profitTab.classList.add("active");
    editTab.classList.remove("active");
  } else {
    profitPanel.classList.add("hidden");
    editPanel.classList.remove("hidden");
    profitTab.classList.remove("active");
    editTab.classList.add("active");
  }
};

window.saveAssetAccounts = async function () {
  const accounts = await getAssetAccounts();

  for (const item of accounts) {
    const quantityInput =
      document.getElementById(`qty-${item.id}`);

    const avgInput =
      document.getElementById(`avg-${item.id}`);

    const quantity = Number(quantityInput.value);
    const avgPrice = Number(avgInput.value);

    await updateDoc(
      doc(db, "accounts", item.id),
      {
        quantity,
        avgPrice
      }
    );
  }

  await renderAssetStatus();
  showAssetTab("profit");

  alert("Firestore에 저장되었습니다.");
};

function loadEtf() {
  if (!etfStock) return;

  const current = Number(etfStock.current || 0);
  const previous = Number(etfStock.previous || 0);
  const open = Number(etfStock.open || 0);
  const high = Number(etfStock.high || 0);
  const low = Number(etfStock.low || 0);
  const volume = Number(etfStock.volume || 0);

  const diff = current - previous;
  const changeRate =
    previous === 0 ? 0 : diff / previous;

  const cls = getChangeClass(diff);

  const etfTable =
    document.getElementById("etfTable");

  if (!etfTable) return;

  const naverButton = etfStock.naverUrl
    ? `
      <button
        class="link-btn"
        onclick="event.stopPropagation(); openNaver('${etfStock.naverUrl}')"
      >
        네이버
      </button>
    `
    : "-";

  etfTable.innerHTML = `
    <tr class="clickable-row" onclick="goDetail('${etfStock.code || ETF_CODE}')">
      <td><span class="badge">${etfStock.type || "ETF"}</span></td>
      <td class="etf-name">${etfStock.name || "KODEX 차이나휴머노이드로봇"}</td>
      <td><span class="badge">${etfStock.code || ETF_CODE}</span></td>
      <td>${formatNumber(current)}</td>
      <td>${formatNumber(previous)}</td>
      <td class="${cls}">${diff > 0 ? "+" : ""}${formatNumber(diff)}</td>
      <td class="${cls}">${changeRate > 0 ? "+" : ""}${(changeRate * 100).toFixed(2)}%</td>
      <td>${formatNumber(open)}</td>
      <td>${formatNumber(high)}</td>
      <td>${formatNumber(low)}</td>
      <td>${formatNumber(volume)}</td>
      <td>${etfStock.market || "한국"}</td>
      <td class="naver-cell">
        <div class="naver-link-wrap">
          ${naverButton}
        </div>
      </td>
    </tr>
  `;
}

function renderStocks() {
  const searchInput =
    document.getElementById("searchInput");

  const sortSelect =
    document.getElementById("sortSelect");

  const tbody =
    document.getElementById("stockTable");

  if (!searchInput || !sortSelect || !tbody) return;

  const keyword =
    searchInput.value.trim().toLowerCase();

  const sortKey = sortSelect.value;

  let stocks = [...componentStocks];

  if (keyword) {
    stocks = stocks.filter(stock =>
      String(stock.name || "")
        .toLowerCase()
        .includes(keyword)
      ||
      String(stock.code || "")
        .toLowerCase()
        .includes(keyword)
    );
  }

  stocks.sort((a, b) => {
    if (sortKey === "changeRate") {
      return Number(b.changeRate) - Number(a.changeRate);
    }

    if (sortKey === "volume") {
      return Number(b.volume) - Number(a.volume);
    }

    return Number(a.rank || 999) - Number(b.rank || 999);
  });

  tbody.innerHTML = "";

  stocks.forEach((stock, index) => {
    const cls = getChangeClass(stock.diff);

    const naverButton = stock.naverUrl
      ? `
        <button
          class="link-btn"
          onclick="event.stopPropagation(); openNaver('${stock.naverUrl}')"
        >
          네이버
        </button>
      `
      : "-";

    tbody.innerHTML += `
      <tr class="clickable-row" onclick="goDetail('${stock.code}')">
        <td>${stock.rank || index + 1}</td>
        <td class="name">${stock.name}</td>
        <td><span class="badge">${stock.code}</span></td>
        <td>${formatPercent(stock.weight)}</td>
        <td>${formatNumber(stock.current)}</td>
        <td>${formatNumber(stock.previous)}</td>
        <td class="${cls}">${stock.diff > 0 ? "+" : ""}${formatNumber(stock.diff)}</td>
        <td class="${cls}">${stock.changeRate > 0 ? "+" : ""}${(stock.changeRate * 100).toFixed(2)}%</td>
        <td>${formatNumber(stock.open)}</td>
        <td>${formatNumber(stock.high)}</td>
        <td>${formatNumber(stock.low)}</td>
        <td>${formatNumber(stock.volume)}</td>
        <td>${stock.market}</td>
        <td class="naver-cell">
          <div class="naver-link-wrap">
            ${naverButton}
          </div>
        </td>
      </tr>
    `;
  });

  updateSummary(stocks);
  updateTimeText();
}

function renderPortfolioChart() {
  const canvas =
    document.getElementById("portfolioChart");

  if (!canvas) return;

  if (portfolioChart) {
    portfolioChart.destroy();
    portfolioChart = null;
  }

  if (!componentStocks.length) return;

  const labels =
    componentStocks.map(stock => stock.name);

  const weights =
    componentStocks.map(stock =>
      Number(stock.weight || 0) * 100
    );

  portfolioChart = new Chart(canvas, {
    type: "doughnut",
    data: {
      labels,
      datasets: [
        {
          label: "비중",
          data: weights,
          borderWidth: 1
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "55%",

      onHover: (event, elements) => {
        const target = event.native?.target;

        if (target) {
          target.style.cursor =
            elements.length ? "pointer" : "default";
        }
      },

      onClick: (event, elements) => {
        if (!elements.length) return;

        const index = elements[0].index;
        const stock = componentStocks[index];

        if (!stock) return;

        goDetail(stock.code);
      },

      plugins: {
        legend: {
          position: "right"
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              return `${context.label}: ${context.raw.toFixed(2)}%`;
            }
          }
        }
      }
    }
  });
}

function updateSummary(stocks) {
  const upCount =
    stocks.filter(s => s.diff > 0).length;

  const downCount =
    stocks.filter(s => s.diff < 0).length;

  const avg =
    stocks.length
      ? stocks.reduce(
          (sum, s) =>
            sum + Number(s.changeRate || 0),
          0
        ) / stocks.length
      : 0;

  document.getElementById("stockCount").innerText =
    stocks.length;

  document.getElementById("upCount").innerText =
    upCount;

  document.getElementById("downCount").innerText =
    downCount;

  const avgEl =
    document.getElementById("avgChange");

  avgEl.innerText =
    (avg * 100).toFixed(2) + "%";

  avgEl.className =
    getChangeClass(avg);
}

function updateTimeText() {
  const updateTime =
    document.getElementById("updateTime");

  if (updateTime) {
    updateTime.innerText =
      new Date().toLocaleString();
  }
}

window.loadStocks = async function () {
  await loadEtfFromFirestore();
  await loadComponentsFromFirestore();
};

document
  .getElementById("searchInput")
  .addEventListener("input", renderStocks);

document
  .getElementById("sortSelect")
  .addEventListener("change", renderStocks);

await loadEtfFromFirestore();
await loadComponentsFromFirestore();

setInterval(async () => {
  await loadEtfFromFirestore();
  await loadComponentsFromFirestore();
}, 30000);
