window.etfStock = {
  type: "ETF",
  name: "KODEX 차이나휴머노이드로봇",
  code: "0045K0",
  current: 10235,
  previous: 10120,
  open: 10180,
  high: 10340,
  low: 10095,
  volume: 125430,
  market: "한국"
};

window.sampleStocks = [
  {
    rank: 1,
    name: "Inovance Technology",
    code: "300124.SZ",
    weight: 0.1025,
    current: 75.08,
    previous: 74.48,
    open: 74.90,
    high: 77.63,
    low: 72.14,
    volume: 53180000,
    market: "중국 심천"
  },
  {
    rank: 2,
    name: "UBTECH Robotics",
    code: "9880.HK",
    weight: 0.0960,
    current: 110.30,
    previous: 111.80,
    open: 111.80,
    high: 116.00,
    low: 107.60,
    volume: 6910000,
    market: "홍콩"
  },
  {
    rank: 3,
    name: "Estun Automation",
    code: "002747.SZ",
    weight: 0.0830,
    current: 18.42,
    previous: 18.10,
    open: 18.20,
    high: 18.75,
    low: 17.88,
    volume: 24500000,
    market: "중국 심천"
  },
  {
    rank: 4,
    name: "Siasun Robot",
    code: "300024.SZ",
    weight: 0.0785,
    current: 12.36,
    previous: 12.54,
    open: 12.60,
    high: 12.88,
    low: 12.20,
    volume: 38100000,
    market: "중국 심천"
  },
  {
    rank: 5,
    name: "Efort Intelligent",
    code: "688165.SS",
    weight: 0.0710,
    current: 9.82,
    previous: 9.75,
    open: 9.76,
    high: 10.05,
    low: 9.61,
    volume: 9150000,
    market: "중국 상해"
  },
  {
    rank: 6,
    name: "Hollysys Automation",
    code: "HOLI",
    weight: 0.0660,
    current: 26.18,
    previous: 26.18,
    open: 26.15,
    high: 26.25,
    low: 26.10,
    volume: 420000,
    market: "미국"
  },
  {
    rank: 7,
    name: "Leader Harmonious Drive",
    code: "688017.SS",
    weight: 0.0615,
    current: 84.50,
    previous: 82.30,
    open: 82.80,
    high: 85.60,
    low: 81.90,
    volume: 3200000,
    market: "중국 상해"
  },
  {
    rank: 8,
    name: "Shanghai STEP Electric",
    code: "002527.SZ",
    weight: 0.0550,
    current: 8.72,
    previous: 8.91,
    open: 8.95,
    high: 9.02,
    low: 8.65,
    volume: 12700000,
    market: "중국 심천"
  },
  {
    rank: 9,
    name: "JAKA Robotics",
    code: "JAKA",
    weight: 0.0480,
    current: 15.10,
    previous: 14.92,
    open: 14.96,
    high: 15.40,
    low: 14.80,
    volume: 6100000,
    market: "비상장/샘플"
  },
  {
    rank: 10,
    name: "Fourier Intelligence",
    code: "FOURIER",
    weight: 0.0410,
    current: 21.30,
    previous: 21.90,
    open: 21.95,
    high: 22.10,
    low: 21.05,
    volume: 2800000,
    market: "비상장/샘플"
  }
];

window.getAllStocks = function () {
  return [window.etfStock, ...window.sampleStocks];
};

window.makeHistory = function (stock) {
  const closes = [];

  let value = Number(stock.previous) || Number(stock.current);

  for (let i = 9; i >= 0; i--) {
    const date = new Date();

    date.setDate(date.getDate() - i);

    value = value * (1 + (Math.sin(i + stock.code.length) * 0.008));

    if (i === 0) {
      value = Number(stock.current);
    }

    closes.push({
      date: date.toISOString().slice(0, 10),
      close: Number(value.toFixed(2)),
      volume: Math.round(
        (stock.volume || 1000000) * (0.75 + i * 0.03)
      )
    });
  }

  return closes;
};