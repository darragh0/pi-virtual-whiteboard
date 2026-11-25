// The Pi's video, one frame at a time
//
// The page asks for a frame only once the last one has shown: frames can never queue up on a slow network, so the
// view stays live and the frame rate drops instead of lag building up. Each frame arrives with the hand found in it
// (X-Hand header), so what's drawn over the video always matches the video

const RETRY_MS = 500;

// Show each frame in `video`, then call onFrame(hand) with its hand and onStats(text) with network stats
export async function streamFrames(video, onFrame, onStats) {
  let [fps, mbps, lag] = [0, 0, 0]; // Smoothed, so the numbers don't flicker
  for (;;) {
    try {
      // fetch() rather than setting img.src to the URL, so the browser doesn't flash "Waiting for localhost..."
      const start = performance.now();
      const response = await fetch("/frame", { cache: "no-store" });
      const frame = await response.blob();
      const url = URL.createObjectURL(frame);
      video.src = url;
      await video.decode();
      URL.revokeObjectURL(url);
      onFrame(JSON.parse(response.headers.get("X-Hand")));

      // Received rate: if well below the Pi's fps, the network is what's holding it back
      // Lag: capture to on screen, minus camera exposure (assumes the Pi's and this device's clocks agree)
      const seconds = (performance.now() - start) / 1000;
      fps = 0.9 * fps + 0.1 / seconds;
      mbps = 0.9 * mbps + (0.1 * (frame.size * 8)) / seconds / 1e6;
      lag = 0.9 * lag + 0.1 * (Date.now() - 1000 * response.headers.get("X-Captured"));
      onStats(`${fps.toFixed(0)} fps · ${mbps.toFixed(1)} Mbit/s · ${lag.toFixed(0)} ms lag`);
    } catch (error) {
      console.error(error); // Usually the app restarting, but a bug drawing the frame would land here too
      onStats("reconnecting...");
      await new Promise((resolve) => setTimeout(resolve, RETRY_MS)); // App restarting: retry
    }
  }
}
