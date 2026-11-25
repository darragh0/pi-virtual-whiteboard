// Turns the hand's gesture each frame into actions on the board (see hands/gestures.py for the gestures)

import { COLOURS } from "./hud.js";

// Landmark numbers: reference/hand_landmarks.png
const THUMB_TIP = 4;
const INDEX_FINGER_TIP = 8;
const PALM = [0, 5, 9, 13, 17]; // Wrist and finger knuckles: their average is the palm's centre

const PEN_WIDTH = 0.012; // In board heights
const ERASER_WIDTH = 0.09;
const CLEAR_HOLD_MS = 1000; // How long a fist must be held to clear the board: long enough not to happen by accident
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
  #fistSince = null; // When the current fist started
  #fistCleared = false; // One clear per fist: open the hand to clear again
  #wheelCentre = null; // Where the current pinch opened the colour wheel
  #wheelChoice = null;
  #lastInk = null; // The last point inked, to tell how far the hand moved during a dropout
  #lost = false; // Whether the hand dropped out since the last frame it was seen

  constructor(board, hud) {
    this.#board = board;
    this.#hud = hud;
  }

  get colour() {
    return this.#colour;
  }

  // Act on one frame's hand: {gesture, landmarks: 21 [x, y] in 0..1 of the board, or null during a dropout}
  update({ gesture, landmarks }, now) {
    if (gesture !== this.#gesture) this.#change(this.#gesture, gesture, now);
    this.#gesture = gesture;

    // During a dropout the gesture holds (so a stroke isn't cut), but there's nowhere to draw: a stroke picks up from
    // its last point when the hand is back
    if (landmarks === null) {
      this.#lost = true;
      this.#hud.drawCursor(null);
      return;
    }

    const tip = landmarks[INDEX_FINGER_TIP];
    switch (gesture) {
      case "draw":
        this.#ink(tip, now);
        this.#hud.drawCursor({ kind: "pen", at: tip, width: PEN_WIDTH, colour: this.#colour.value });
        break;
      case "erase": {
        const palm = average(PALM.map((index) => landmarks[index]));
        this.#board.extend(palm, now);
        this.#hud.drawCursor({ kind: "eraser", at: palm, width: ERASER_WIDTH });
        break;
      }
      case "pinch": {
        const pinch = average([landmarks[THUMB_TIP], tip]);
        this.#wheelCentre ??= pinch;
        this.#wheelChoice = this.#hud.wheelChoice(this.#wheelCentre, pinch);
        this.#hud.drawCursor({ kind: "wheel", centre: this.#wheelCentre, choice: this.#wheelChoice });
        break;
      }
      case "fist":
        this.#holdFist(average(PALM.map((index) => landmarks[index])), now);
        break;
      default: // hover, none
        this.#hud.drawCursor({ kind: "hover", at: tip, colour: this.#colour.value });
    }
    this.#lost = false;
  }

  // Leaving one gesture for another: finish what the old one was doing, start what the new one does
  #change(from, to, now) {
    // Losing the hand reads as "none" too, but then there are no in-between shapes to trim
    this.#board.end(to === "none" && this.#lost ? Infinity : now - GESTURE_HOLD_MS);
    this.#lastInk = null;

    if (from === "pinch") this.#pickColour();
    if (from === "fist") [this.#fistSince, this.#fistCleared] = [null, false];

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

  #pickColour() {
    if (this.#wheelChoice !== null) {
      this.#colour = COLOURS[this.#wheelChoice];
      this.#hud.toast(this.#colour.name);
    }
    this.#wheelCentre = this.#wheelChoice = null;
  }

  #holdFist(palm, now) {
    if (this.#fistCleared) {
      this.#hud.drawCursor(null);
      return;
    }

    this.#fistSince ??= now;
    const progress = Math.min(1, (now - this.#fistSince) / CLEAR_HOLD_MS);
    this.#hud.drawCursor({ kind: "clearing", at: palm, progress });
    if (progress === 1) {
      this.clear();
      this.#fistCleared = true;
    }
  }

  clear() {
    const cleared = this.#board.clear();
    if (cleared) this.#hud.toast("Board cleared · Z to undo");
  }
}
