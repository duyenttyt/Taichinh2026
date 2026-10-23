// Firebase SDK Initialization for HomeFinance (taichinhdemo-1ce08)
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getAnalytics, logEvent } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-analytics.js";
import { getFirestore, doc, setDoc, getDoc } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js";

// Firebase configuration provided for taichinhdemo-1ce08
export const firebaseConfig = {
  apiKey: "AIzaSyDiO_rM-If2tERIZGETGHh_bSUoqHN9jI8",
  authDomain: "taichinhdemo-1ce08.firebaseapp.com",
  projectId: "taichinhdemo-1ce08",
  storageBucket: "taichinhdemo-1ce08.firebasestorage.app",
  messagingSenderId: "292869093804",
  appId: "1:292869093804:web:b18c2d011c0176753f2209",
  measurementId: "G-5GHBFVCB0E"
};

// Initialize Firebase App
export const app = initializeApp(firebaseConfig);

// Initialize Firebase Analytics
export let analytics = null;
try {
  analytics = getAnalytics(app);
  logEvent(analytics, 'page_view', { page_title: document.title });
  console.log("Firebase Analytics đã được kích hoạt thành công!");
} catch (e) {
  console.warn("Firebase Analytics khởi tạo:", e);
}

// Initialize Firestore (Ready for Cloud Sync)
export const db = getFirestore(app);

// Expose to window for global access
window.firebaseApp = app;
window.firebaseAnalytics = analytics;
window.firebaseDb = db;
window.logFirebaseEvent = (eventName, params) => {
  if (analytics) {
    logEvent(analytics, eventName, params);
  }
};
