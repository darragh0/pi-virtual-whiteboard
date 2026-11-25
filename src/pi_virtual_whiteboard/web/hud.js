// Everything drawn over the board that isn't the drawing: the cursor, colour wheel and messages

export const COLOURS = [
  { name: "Pink", value: "#ff2bd6" },
  { name: "Orange", value: "#ff8a2b" },
  { name: "Gold", value: "#ffd12b" },
  { name: "Mint", value: "#4dffb8" },
  { name: "Ocean", value: "#2bd9ff" },
  { name: "Violet", value: "#a45bff" },
  { name: "White", value: "#ffffff" },
];

// Colour wheel, in board heights: swatches sit on a ring around where the pinch started
const WHEEL_RADIUS = 0.11;
const SWATCH_RADIUS = 0.028;
const WHEEL_DEAD_ZONE = 0.035; // Closer to the centre than this picks nothing, so a pinch can be let go to cancel

const TOAST_MS = 1800;

export class Hud {
  #cursor;
  #context;
  #toast;
  #toastTimer;

  constructor({ cursor, toast }) {
    this.#cursor = cursor;
    this.#context = cursor.getContext("2d");
    this.#toast = toast;
    new ResizeObserver(() => {
      const scale = window.devicePixelRatio;
      cursor.width = Math.round(cursor.clientWidth * scale);
      cursor.height = Math.round(cursor.clientHeight * scale);
    }).observe(cursor);
  }

  // Board width over height: positions are in 0..1 of each, so a circle needs both to stay round
  get aspect() {
    return this.#cursor.width / this.#cursor.height || 4 / 3;
  }

  // Draw the cursor layer for this frame. cursor: {kind: "pen" | "hover" | "eraser" | "clearing" | "wheel", ...}
  drawCursor(cursor) {
    const context = this.#context;
    const [w, h] = [this.#cursor.width, this.#cursor.height];
    context.clearRect(0, 0, w, h);
    if (cursor === null) return;
    if (cursor.kind === "wheel") {
      this.#drawWheel(cursor); // Placed by its centre, not a cursor position
      return;
    }

    const [x, y] = [cursor.at[0] * w, cursor.at[1] * h];
    context.lineWidth = 0.004 * h;
    switch (cursor.kind) {
      case "pen":
        this.#ring(x, y, cursor.width * h * 0.5 + 0.006 * h, "#000a");
        this.#dot(x, y, cursor.width * h * 0.5, cursor.colour);
        break;
      case "hover":
        this.#ring(x, y, 0.014 * h, cursor.colour);
        break;
      case "eraser":
        this.#ring(x, y, cursor.width * h * 0.5, "#fff");
        break;
      case "clearing":
        this.#ring(x, y, 0.05 * h, "#fff4");
        context.lineWidth = 0.012 * h;
        context.beginPath();
        context.arc(x, y, 0.05 * h, -Math.PI / 2, -Math.PI / 2 + cursor.progress * 2 * Math.PI);
        context.strokeStyle = "#ff3b3b";
        context.stroke();
        break;
    }
  }

  // Which colour (index into COLOURS) a pinch moved from `centre` to `at` points to, or null in the dead zone
  wheelChoice(centre, at) {
    const dx = (at[0] - centre[0]) * this.aspect; // In board heights, like dy
    const dy = at[1] - centre[1];
    if (Math.hypot(dx, dy) < WHEEL_DEAD_ZONE) return null;

    const turn = (Math.atan2(dy, dx) + Math.PI / 2) / (2 * Math.PI); // 0 at the top, clockwise
    return Math.round((turn + 1) * COLOURS.length) % COLOURS.length;
  }

  #drawWheel({ centre, choice }) {
    const [w, h] = [this.#cursor.width, this.#cursor.height];
    const [cx, cy] = [centre[0] * w, centre[1] * h];
    this.#dot(cx, cy, WHEEL_RADIUS * h * 1.45, "#0009");
    COLOURS.forEach(({ value }, index) => {
      const angle = (index / COLOURS.length) * 2 * Math.PI - Math.PI / 2;
      const [x, y] = [cx + Math.cos(angle) * WHEEL_RADIUS * h, cy + Math.sin(angle) * WHEEL_RADIUS * h];
      const chosen = index === choice;
      this.#dot(x, y, SWATCH_RADIUS * h * (chosen ? 1.4 : 1), value);
      if (chosen) this.#ring(x, y, SWATCH_RADIUS * h * 1.4 + 0.006 * h, "#fff");
    });
  }

  #dot(x, y, radius, colour) {
    const context = this.#context;
    context.beginPath();
    context.arc(x, y, radius, 0, 2 * Math.PI);
    context.fillStyle = colour;
    context.fill();
  }

  #ring(x, y, radius, colour) {
    const context = this.#context;
    context.beginPath();
    context.arc(x, y, radius, 0, 2 * Math.PI);
    context.strokeStyle = colour;
    context.stroke();
  }

  toast(text) {
    this.#toast.textContent = text;
    flash(this.#toast);
    clearTimeout(this.#toastTimer);
    this.#toastTimer = setTimeout(() => (this.#toast.textContent = ""), TOAST_MS);
  }
}

// Restart an element's "flash" CSS animation
function flash(element) {
  element.classList.remove("flash");
  void element.offsetWidth; // Forces a style recalculation, without which removing and re-adding is a no-op
  element.classList.add("flash");
}
