// Turns the hand's gesture each frame into actions on the board (see hands/gestures.py for the gestures)

// Landmark numbers: reference/hand_landmarks.png
const THUMB_TIP = 4;
const INDEX_FINGER_TIP = 8;
const PALM = [0, 5, 9, 13, 17]; // Wrist and finger knuckles: their average is the palm's centre

// Picked with keys 1-7 (or the swatches below the board), in this order
export const COLOURS = [
  { name: "White", value: "#ffffff" },
  { name: "Pink", value: "#ff2bd6" },
  { name: "Orange", value: "#ff8a2b" },
  { name: "Gold", value: "#ffd12b" },
  { name: "Mint", value: "#4dffb8" },
  { name: "Ocean", value: "#2bd9ff" },
  { name: "Violet", value: "#a45bff" },
];

const PEN_WIDTH = 0.012; // In board heights
const ERASER_WIDTH = 0.09;
// A new gesture only takes over once held this long (GESTURE_HOLD_S in config.py), so a stroke's last this-many ms
// were drawn while the hand was already changing shape: they're trimmed off, or the stroke ends in a stray flick
const GESTURE_HOLD_MS = 120;
// After a dropout, a stroke carries on in a straight line from where the hand was lost: fine for a blip, but if the
// hand comes back further away than this (board heights), it starts a new stroke instead
const MAX_BRIDGE = 0.08;

const average = (points) => [0, 1].map((axis) => points.reduce((sum, point) => sum + point[axis], 0) / points.length);

export class Controls {
  #board;
  #hud;
  #colour = COLOURS[0];
  #gesture = "none";
  #lastInk = null; // The last point inked, to tell how far the hand moved during a dropout
  #lost = false; // Whether the hand dropped out since the last frame it was seen

  constructor(board, hud) {
    this.#board = board;
    this.#hud = hud;
  }

  get colour() {
    return this.#colour;
  }

  set colour(colour) {
    this.#colour = colour;
    if (this.#gesture === "draw") this.#board.begin("pen", colour.value, PEN_WIDTH); // Mid-stroke: carry on in it
  }

  // Act on one frame's hand: {gesture, landmarks: 21 [x, y] in 0..1 of the board, or null during a dropout}
  update({ gesture, landmarks }, now) {
    if (gesture !== this.#gesture) this.#change(gesture, now);
    this.#gesture = gesture;

    // During a dropout the gesture holds (so a stroke isn't cut), but there's nowhere to draw: a stroke picks up from
    // its last point when the hand is back
    if (landmarks === null) {
      this.#lost = true;
      this.#hud.drawCursor(null);
      return;
    }

    // The pen is where the fingertips meet, whether pinched or not, so it doesn't jump when the pinch closes
    const pen = average([landmarks[THUMB_TIP], landmarks[INDEX_FINGER_TIP]]);
    switch (gesture) {
      case "draw":
        this.#ink(pen, now);
        this.#hud.drawCursor({ kind: "pen", at: pen, width: PEN_WIDTH, colour: this.#colour.value });
        break;
      case "erase": {
        const palm = average(PALM.map((index) => landmarks[index]));
        this.#board.extend(palm, now);
        this.#hud.drawCursor({ kind: "eraser", at: palm, width: ERASER_WIDTH });
        break;
      }
      default: // none: just move
        this.#hud.drawCursor({ kind: "move", at: pen, colour: this.#colour.value });
    }
    this.#lost = false;
  }

  // Leaving one gesture for another: finish what the old one was doing, start what the new one does
  #change(to, now) {
    // Losing the hand reads as "none" too, but then there are no in-between shapes to trim
    this.#board.end(to === "none" && this.#lost ? Infinity : now - GESTURE_HOLD_MS);
    this.#lastInk = null;

    if (to === "draw") this.#board.begin("pen", this.#colour.value, PEN_WIDTH);
    if (to === "erase") this.#board.begin("eraser", "#000", ERASER_WIDTH);
  }

  #ink(point, now) {
    if (this.#lastInk !== null) {
      const [dx, dy] = [(point[0] - this.#lastInk[0]) * this.#hud.aspect, point[1] - this.#lastInk[1]];
      if (this.#lost && Math.hypot(dx, dy) > MAX_BRIDGE) {
        this.#board.begin("pen", this.#colour.value, PEN_WIDTH); // Too far to join up: a new stroke
      }
    }
    this.#board.extend(point, now);
    this.#lastInk = point;
  }
}
