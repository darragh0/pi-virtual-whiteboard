// The drawing itself
//
// Strokes are kept as data, in 0..1 of the board's width and height (like the hand's landmarks), and drawn onto a
// canvas from it: the drawing stays sharp at any window size, and undo is just dropping the last action and
// redrawing. Erasing and clearing are actions in the same list, so they undo like any stroke

const MIN_STEP = 0.002; // Points closer than this to the last are skipped: at rest, the fingertip only jitters

const midpoint = ([ax, ay], [bx, by]) => [(ax + bx) / 2, (ay + by) / 2];

export class Board {
  #canvas;
  #context;
  #actions = []; // Strokes ({tool: "pen" | "eraser", colour, width, points}) and clears ({tool: "clear"})
  #undone = [];
  #live = null; // The stroke being drawn

  constructor(canvas) {
    this.#canvas = canvas;
    this.#context = canvas.getContext("2d");
    new ResizeObserver(() => this.#resize()).observe(canvas);
  }

  get drawing() {
    return this.#live !== null;
  }

  // Start a stroke. width is in board heights
  begin(tool, colour, width) {
    this.end();
    this.#live = { tool, colour, width, points: [], times: [] };
  }

  // Add a point, seen at time `now` (ms), to the stroke, drawing the new piece straight away
  extend(point, now) {
    const live = this.#live;
    if (live === null) return;

    const last = live.points.at(-1);
    if (last !== undefined && Math.hypot(point[0] - last[0], point[1] - last[1]) < MIN_STEP) return;

    live.points.push(point);
    live.times.push(now);
    this.#drawPiece(live, live.points.length - 1);
  }

  // Finish the stroke, dropping any points seen after `trimAfter` (ms)
  end(trimAfter = Infinity) {
    const live = this.#live;
    this.#live = null;
    if (live === null) return;

    const kept = live.times.findLastIndex((time) => time <= trimAfter) + 1;
    const stroke = { tool: live.tool, colour: live.colour, width: live.width, points: live.points.slice(0, kept) };
    if (stroke.points.length > 0) this.#do(stroke);

    if (kept < live.points.length)
      this.#redraw(); // Already drawn as they came, so redraw without them
    else this.#drawTail(stroke);
  }

  // Clear the board (undoable). Returns whether there was anything to clear
  clear() {
    return this.#between(() => {
      const lastClear = this.#actions.findLastIndex((action) => action.tool === "clear");
      if (lastClear === this.#actions.length - 1) return false;
      this.#do({ tool: "clear" });
      return true;
    });
  }

  undo() {
    return this.#between(() => {
      if (this.#actions.length === 0) return false;
      this.#undone.push(this.#actions.pop());
      return true;
    });
  }

  redo() {
    return this.#between(() => {
      if (this.#undone.length === 0) return false;
      this.#actions.push(this.#undone.pop());
      return true;
    });
  }

  // Finish the stroke being drawn, make a change (returning whether it changed anything), redraw, then carry on in a
  // fresh stroke: the hand is still drawing, and a stroke begins only when the gesture changes
  #between(change) {
    const live = this.#live;
    this.end();
    const changed = change();
    this.#redraw();
    if (live !== null) this.begin(live.tool, live.colour, live.width);
    return changed;
  }

  #do(action) {
    this.#actions.push(action);
    this.#undone = []; // A new action replaces whatever was undone, as in any editor
  }

  // Match the canvas's pixels to the screen's, so strokes stay sharp at any size
  #resize() {
    const scale = window.devicePixelRatio;
    this.#canvas.width = Math.round(this.#canvas.clientWidth * scale);
    this.#canvas.height = Math.round(this.#canvas.clientHeight * scale);
    this.#redraw();
  }

  #redraw() {
    this.#context.clearRect(0, 0, this.#canvas.width, this.#canvas.height);
    for (const action of this.#actions) {
      if (action.tool === "clear") {
        this.#context.clearRect(0, 0, this.#canvas.width, this.#canvas.height);
        continue;
      }
      action.points.forEach((_, index) => this.#drawPiece(action, index));
      this.#drawTail(action);
    }
    if (this.#live !== null) this.#live.points.forEach((_, index) => this.#drawPiece(this.#live, index));
  }

  // Strokes curve through the midpoints between points (each point is a curve's control point), which smooths out
  // the corners between frames. Piece `index` is the curve that point `index` completes
  #drawPiece(stroke, index) {
    const points = stroke.points;
    const context = this.#style(stroke);
    const [w, h] = [this.#canvas.width, this.#canvas.height];

    context.beginPath();
    if (index === 0) {
      const [x, y] = points[0];
      context.arc(x * w, y * h, (stroke.width * h) / 2, 0, 2 * Math.PI); // A dot, for a tap
      context.fill();
      return;
    }

    const [startX, startY] = index === 1 ? points[0] : midpoint(points[index - 2], points[index - 1]);
    const [controlX, controlY] = points[index - 1];
    const [endX, endY] = midpoint(points[index - 1], points[index]);
    context.moveTo(startX * w, startY * h);
    context.quadraticCurveTo(controlX * w, controlY * h, endX * w, endY * h);
    context.stroke();
  }

  // The last half-segment, from the last midpoint to the last point: drawn once the stroke ends
  #drawTail(stroke) {
    const points = stroke.points;
    if (points.length < 2) return;

    const context = this.#style(stroke);
    const [w, h] = [this.#canvas.width, this.#canvas.height];
    const [startX, startY] = midpoint(points.at(-2), points.at(-1));
    const [endX, endY] = points.at(-1);
    context.beginPath();
    context.moveTo(startX * w, startY * h);
    context.lineTo(endX * w, endY * h);
    context.stroke();
  }

  #style(stroke) {
    const context = this.#context;
    // The eraser removes ink rather than painting over it, so the video still shows through where it erased
    context.globalCompositeOperation = stroke.tool === "eraser" ? "destination-out" : "source-over";
    context.strokeStyle = context.fillStyle = stroke.colour;
    context.lineWidth = stroke.width * this.#canvas.height;
    context.lineCap = context.lineJoin = "round";
    return context;
  }
}
