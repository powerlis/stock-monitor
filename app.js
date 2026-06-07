import { db } from "./firebase-config.js";

import {
  collection,
  getDocs,
  doc,
  getDoc,
  updateDoc
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

// 구성종목은 아직 data.js 샘플 사용
const sampleStocks = window.sampleStocks;

// ETF 실제 종목코드
const ETF_CODE = "0048K0";

// ETF 데이터는 Firestore에서 가져와서 여기에 저장
let etfStock = window.etfStock;

function formatNumber(value) {
  if (value === null || value === undefined || isNaN(value)) return "-";
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 });
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

// Firestore에서 ETF 현재가 읽기
async function loadEtfFromFirestore() {
  try {
    const docRef = doc(db, "stocks", ETF_CODE);
    const docSnap = await getDoc(docRef);

    if (docSnap.exists()) {
      etfStock = docSnap.data();
      window.etfStock = etfStock;

      loadEtf();
      await renderAssetStatus();

      console.log("ETF Firestore 데이터 불러오기 성공:", etfStock);
    } else {
      console.log(`Firestore에 stocks/${ETF_CODE} 문서가 없습니다.`);

      etfStock = {
        type: "ETF",
        name: "KODEX 차이나휴머노이드로봇",
        code: ETF_CODE,
        current: 0,
        previous: 0,
        open: 0,
        high: 0,
        low: 0,
        volume: 0,
        market: "한국"
      };

      window.etfStock = etfStock;

      loadEtf();
      await renderAssetStatus();
    }
  } catch (error) {
    console.error("ETF Firestore 데이터 불러오기 실패:", error);

    etfStock = window.etfStock || {
      type: "ETF",
      name: "KODEX 차이나휴머노이드로봇",
      code: ETF_CODE,
      current: 0,
      previous: 0,
      open: 0,
      high: 0,
      low: 0,
      volume: 0,
      market: "한국"
    };

    loadEtf();
    await renderAssetStatus();
  }
}

// Firestore에서 계좌 데이터 읽기
async function getAssetAccounts() {
  const querySnapshot = await getDocs(collection(db, "accounts"));

  const accounts = [];

  querySnapshot.forEach((docSnap) => {
    accounts.push({
      id: docSnap.id,
      ...docSnap.data()
    });
  });

  accounts.sort((a, b) => Number(a.order) - Number(b.order));

  return accounts;
}

// 자산현황 표시
async function renderAssetStatus() {
  if (!etfStock) return;

  const accounts = await getAssetAccounts();
  const currentPrice = Number(etfStock.current);

  const profitTable = document.getElementById("assetProfitTable");
  const editTable = document.getElementById("assetEditTable");

  if (!profitTable || !editTable) return;

  profitTable.innerHTML = "";
  editTable.innerHTML = "";

  accounts.forEach((item) => {
    const quantity = Number(item.quantity);
    const avgPrice = Number(item.avgPrice);

    const profit = (currentPrice - avgPrice) * quantity;

    const profitRate = avgPrice === 0
      ? 0
      : ((currentPrice - avgPrice) / avgPrice) * 100;

    const profitClass = profit >= 0 ? "profit-plus" : "profit-minus";

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

// 자산현황 탭 전환
window.showAssetTab = function (tab) {
  const profitPanel = document.getElementById("profitPanel");
  const editPanel = document.getElementById("editPanel");
  const profitTab = document.getElementById("profitTab");
  const editTab = document.getElementById("editTab");

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

// Firestore에 매입단가/주식수 저장
window.saveAssetAccounts = async function () {
  const accounts = await getAssetAccounts();

  for (const item of accounts) {
    const quantityInput = document.getElementById(`qty-${item.id}`);
    const avgInput = document.getElementById(`avg-${item.id}`);

    const quantity = Number(quantityInput.value);
    const avgPrice = Number(avgInput.value);

    await updateDoc(doc(db, "accounts", item.id), {
      quantity: quantity,
      avgPrice: avgPrice
    });
  }

  await renderAssetStatus();
  showAssetTab("profit");

  alert("Firestore에 저장되었습니다.");
};

function loadEtf() {
  if (!etfStock) return;

  const current = Number(etfStock.current);
  const previous = Number(etfStock.previous);
  const open = Number(etfStock.open);
  const high = Number(etfStock.high);
  const low = Number(etfStock.low);
  const volume = Number(etfStock.volume);

  const diff = current - previous;

  const changeRate = previous === 0
    ? 0
    : diff / previous;

  const cls = getChangeClass(diff);

  const etfTable = document.getElementById("etfTable");
  if (!etfTable) return;

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
    </tr>
  `;
}

function loadStocks() {
  if (!sampleStocks) {
    console.error("sampleStocks 데이터를 찾을 수 없습니다.");
    return;
  }

  const searchInput = document.getElementById("searchInput");
  const sortSelect = document.getElementById("sortSelect");
  const tbody = document.getElementById("stockTable");

  if (!searchInput || !sortSelect || !tbody) return;

  const keyword = searchInput.value.trim().toLowerCase();
  const sortKey = sortSelect.value;

  let stocks = [...sampleStocks].map(stock => {
    const diff = stock.current - stock.previous;

    const changeRate = stock.previous === 0
      ? 0
      : diff / stock.previous;

    return {
      ...stock,
      diff,
      changeRate
    };
  });

  if (keyword) {
    stocks = stocks.filter(stock =>
      stock.name.toLowerCase().includes(keyword) ||
      stock.code.toLowerCase().includes(keyword)
    );
  }

  stocks.sort((a, b) => {
    if (sortKey === "changeRate") return b.changeRate - a.changeRate;
    if (sortKey === "volume") return b.volume - a.volume;
    return b.weight - a.weight;
  });

  tbody.innerHTML = "";

  stocks.forEach((stock, index) => {
    const cls = getChangeClass(stock.diff);

    tbody.innerHTML += `
      <tr class="clickable-row" onclick="goDetail('${stock.code}')">
        <td>${index + 1}</td>
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
      </tr>
    `;
  });

  updateSummary(stocks);

  const updateTime = document.getElementById("updateTime");
  if (updateTime) {
    const etfTime = etfStock?.updatedAt ? ` / ETF 갱신: ${etfStock.updatedAt}` : "";
    updateTime.innerText = new Date().toLocaleString() + etfTime;
  }
}

function updateSummary(stocks) {
  const upCount = stocks.filter(s => s.diff > 0).length;
  const downCount = stocks.filter(s => s.diff < 0).length;

  const avg = stocks.length
    ? stocks.reduce((sum, s) => sum + s.changeRate, 0) / stocks.length
    : 0;

  document.getElementById("stockCount").innerText = stocks.length;
  document.getElementById("upCount").innerText = upCount;
  document.getElementById("downCount").innerText = downCount;

  const avgEl = document.getElementById("avgChange");
  avgEl.innerText = (avg * 100).toFixed(2) + "%";
  avgEl.className = getChangeClass(avg);
}

window.loadStocks = async function () {
  await loadEtfFromFirestore();
  loadStocks();
};

document.getElementById("searchInput").addEventListener("input", loadStocks);
document.getElementById("sortSelect").addEventListener("change", loadStocks);

// 최초 실행
await loadEtfFromFirestore();
loadStocks();

// 30초마다 Firestore ETF 현재가 다시 읽기
setInterval(async () => {
  await loadEtfFromFirestore();
  loadStocks();
}, 30000);