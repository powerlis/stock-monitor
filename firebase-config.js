// Firebase SDK
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";

import { getFirestore } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore.js";

// Firebase 설정
const firebaseConfig = {
  apiKey: "AIzaSyCiR-K8JefSRRdcWFMeVsMbwi7ko2Zuf-g",
  authDomain: "kodex-stock-monitor.firebaseapp.com",
  projectId: "kodex-stock-monitor",
  storageBucket: "kodex-stock-monitor.firebasestorage.app",
  messagingSenderId: "197734184067",
  appId: "1:197734184067:web:7a7579634fafd8c41e57b6",
  measurementId: "G-B95FMBE0MM"
};

// Firebase 초기화
const app = initializeApp(firebaseConfig);

// Firestore 객체 생성
export const db = getFirestore(app);

console.log("Firebase 연결 성공");