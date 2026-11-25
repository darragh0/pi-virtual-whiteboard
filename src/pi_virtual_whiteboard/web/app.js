// Shows the Pi's video with the tracked hand drawn over it
//
// The page asks for one frame at a time, and only once the last one has shown: frames can never queue up on a
// slow network, so the view stays live and the frame rate drops instead of lag building up. Each frame arrives
// with the hand found in it (X-Hand header), so what's drawn over the video always matches the video

const INDEX_FINGER_TIP = 8; // Landmark numbering: reference/hand_landmarks.png

const board = document.getElementById("board");
const video = document.getElementById("video");
const overlay = document.getElementById("overlay");
const stats = document.getElementById("stats");
const context = overlay.getContext("2d");

// Match the canvas's pixels to the screen's, so what's drawn on it stays sharp at any size
function resizeOverlay() {
  const scale = window.devicePixelRatio;
  overlay.width = Math.round(overlay.clientWidth * scale);
  overlay.height = Math.round(overlay.clientHeight * scale);
}
new ResizeObserver(resizeOverlay).observe(overlay);

// The fingertip marker's colour for each gesture (see hands/gestures.py), so you can see what's being read
const GESTURE_COLOURS = {
  draw: "#ff2bd6",
  hover: "#2bd9ff",
  erase: "#ffffff",
  pinch: "#ffd12b",
  fist: "#ff4b2b",
  none: "#888888",
};

// hand: {hand: "left" | "right" | null, gesture, landmarks: [[x, y], ...] in 0..1 of the frame's size, or null}
// The gesture outlasts a brief dropout, so it can be set while landmarks are null
function drawOverlay(hand) {
  context.clearRect(0, 0, overlay.width, overlay.height);
  if (hand.landmarks === null) return;

  const [x, y] = hand.landmarks[INDEX_FINGER_TIP];
  const [px, py, radius] = [x * overlay.width, y * overlay.height, 0.015 * overlay.height];
  context.fillStyle = GESTURE_COLOURS[hand.gesture];
  context.beginPath();
  context.arc(px, py, radius, 0, 2 * Math.PI);
  context.fill();

  context.font = `bold ${Math.round(2 * radius)}px monospace`;
  context.fillText(hand.gesture, px + 1.5 * radius, py - 1.5 * radius);
}

async function showFrame(response) {
  const frame = await response.blob();
  const url = URL.createObjectURL(frame);
  video.src = url;
  await video.decode();
  URL.revokeObjectURL(url);

  board.style.setProperty("--aspect", video.naturalWidth / video.naturalHeight);
  drawOverlay(JSON.parse(response.headers.get("X-Hand")));
  return frame.size;
}

(async () => {
  let [fps, mbps, lag] = [0, 0, 0]; // Smoothed, so the numbers don't flicker
  for (;;) {
    try {
      // fetch() rather than setting img.src to the URL, so the browser doesn't flash "Waiting for localhost..."
      const start = performance.now();
      const response = await fetch("/frame", { cache: "no-store" });
      const bytes = await showFrame(response);

      // Received rate: if well below the fps on the video, the network is what's holding it back
      // Lag: capture to on screen, minus camera exposure (assumes the Pi's and this device's clocks agree)
      const seconds = (performance.now() - start) / 1000;
      fps = 0.9 * fps + 0.1 / seconds;
      mbps = 0.9 * mbps + (0.1 * (bytes * 8)) / seconds / 1e6;
      lag = 0.9 * lag + 0.1 * (Date.now() - 1000 * response.headers.get("X-Captured"));
      stats.textContent = `network: ${fps.toFixed(0)} fps received, ${mbps.toFixed(1)} Mbit/s, ${lag.toFixed(0)} ms lag`;
    } catch {
      stats.textContent = "reconnecting...";
      await new Promise((resolve) => setTimeout(resolve, 500)); // App restarting: retry
    }
  }
})();
