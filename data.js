window.etfStock = {
  type: "ETF",
  name: "KODEX 차이나휴머노이드로봇",
  code: "0048K0",
  current: 0,
  previous: 0,
  open: 0,
  high: 0,
  low: 0,
  volume: 0,
  market: "한국"
};

window.sampleStocks = [
  { rank: 1, name: "Inovance Technology(회천기술)", code: "300124.SZ", weight: 0.09, current: 0, previous: 0, open: 0, high: 0, low: 0, volume: 0, market: "중국 심천" },
  { rank: 2, name: "UBTECH Robotics(유비테크 로보틱스)", code: "9880.HK", weight: 0.0836, current: 0, previous: 0, open: 0, high: 0, low: 0, volume: 0, market: "홍콩" },
  { rank: 3, name: "Ningbo Tuopu Group(탁보그룹)", code: "601689.SH", weight: 0.082, current: 0, previous: 0, open: 0, high: 0, low: 0, volume: 0, market: "중국 상해" },
  { rank: 4, name: "DOBOT(도봇)", code: "2432.HK", weight: 0.0638, current: 0, previous: 0, open: 0, high: 0, low: 0, volume: 0, market: "홍콩" },
  { rank: 5, name: "Leader Harmonious Drive Systems(녹적해파)", code: "688017.SH", weight: 0.0606, current: 0, previous: 0, open: 0, high: 0, low: 0, volume: 0, market: "중국 상해" },
  { rank: 6, name: "Estun Automation(어사돈자동화)", code: "002747.SZ", weight: 0.05, current: 0, previous: 0, open: 0, high: 0, low: 0, volume: 0, market: "중국 심천" },
  { rank: 7, name: "Siasun Robot & Automation(신송로봇)", code: "300024.SZ", weight: 0.05, current: 0, previous: 0, open: 0, high: 0, low: 0, volume: 0, market: "중국 심천" },
  { rank: 8, name: "Shenzhen Megmeet(맥격미특전기)", code: "002851.SZ", weight: 0.045, current: 0, previous: 0, open: 0, high: 0, low: 0, volume: 0, market: "중국 심천" },
  { rank: 9, name: "Efort Intelligent Equipment(애부특지능기인)", code: "688165.SH", weight: 0.04, current: 0, previous: 0, open: 0, high: 0, low: 0, volume: 0, market: "중국 상해" },
  { rank: 10, name: "Zhejiang Sanhua Intelligent(삼화)", code: "002050.SZ", weight: 0.04, current: 0, previous: 0, open: 0, high: 0, low: 0, volume: 0, market: "중국 심천" }
];

window.getAllStocks = function () {
  return [window.etfStock, ...window.sampleStocks];
};

window.makeHistory = function (stock) {
  return [];
};