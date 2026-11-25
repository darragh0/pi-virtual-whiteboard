// Everything drawn over the board that isn't the drawing: the cursor and messages

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

  // Draw the cursor layer for this frame. cursor: {kind: "pen" | "move" | "eraser", at, ...}
  drawCursor(cursor) {
    const context = this.#context;
    const [w, h] = [this.#cursor.width, this.#cursor.height];
    context.clearRect(0, 0, w, h);
    if (cursor === null) return;

    const [x, y] = [cursor.at[0] * w, cursor.at[1] * h];
    context.lineWidth = 0.004 * h;
    switch (cursor.kind) {
      case "pen":
        this.#ring(x, y, cursor.width * h * 0.5 + 0.006 * h, "#000a");
        this.#dot(x, y, cursor.width * h * 0.5, cursor.colour);
        break;
      case "move":
        this.#ring(x, y, 0.014 * h, cursor.colour);
        break;
      case "eraser":
        this.#ring(x, y, cursor.width * h * 0.5, "#fff");
        break;
    }
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
