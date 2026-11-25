// The virtual whiteboard: the Pi's video, with what the hand draws on top

import { Board } from "./board.js";
import { COLOURS, Controls } from "./controls.js";
import { Hud } from "./hud.js";
import { streamFrames } from "./stream.js";

const VIEWS = ["camera", "dim", "board"]; // Behind the ink: the video as is, dimmed, or hidden
const SAVE_BACKGROUND = "#000";

const element = (id) => document.getElementById(id);
const boardElement = element("board");
const video = element("video");
const ink = element("ink");

const board = new Board(ink);
const hud = new Hud({ cursor: element("cursor"), toast: element("toast") });
const controls = new Controls(board, hud);
const gestureChips = document.querySelectorAll("#gestures [data-gesture]");

// How to draw and move, per --mode (shown under the toolbar's gestures)
const HINTS = {
  thumb: { draw: "Point, thumb tucked in", move: "Thumb out" },
  space: { draw: "Hold Space", move: "Let go of Space" },
};
// One swatch per colour, numbered like its key
const swatches = COLOURS.map((colour, index) => {
  const swatch = document.createElement("button");
  swatch.type = "button";
  swatch.title = colour.name;
  swatch.textContent = index + 1;
  swatch.style.background = colour.value;
  swatch.addEventListener("click", () => pickColour(index));
  element("colours").append(swatch);
  return swatch;
});

function pickColour(index) {
  controls.colour = COLOURS[index];
  swatches.forEach((swatch, other) =>
    swatch.classList.toggle("active", other === index),
  );
}
pickColour(0);

function onFrame(hand) {
  boardElement.style.setProperty(
    "--aspect",
    video.naturalWidth / video.naturalHeight,
  );
  controls.update(hand, performance.now());

  for (const hint of document.querySelectorAll("[data-hint]"))
    hint.textContent = HINTS[hand.mode][hint.dataset.hint];

  element("fps").textContent = `${hand.fps} fps`; // The Pi's video: frames tracked per second
  const debug = element("debug"); // Sent only with --debug
  debug.hidden = hand.debug === null;
  if (hand.debug !== null) debug.textContent = hand.debug.join("\n");

  for (const chip of gestureChips)
    chip.classList.toggle("active", chip.dataset.gesture === controls.gesture);
}

// The drawing as a PNG, on the board's background (the video isn't included)
function save() {
  const image = document.createElement("canvas");
  [image.width, image.height] = [ink.width, ink.height];
  const context = image.getContext("2d");
  context.fillStyle = SAVE_BACKGROUND;
  context.fillRect(0, 0, image.width, image.height);
  context.drawImage(ink, 0, 0);

  const link = document.createElement("a");
  link.download = `whiteboard-${new Date().toISOString().slice(0, 19).replaceAll(":", "-")}.png`;
  link.href = image.toDataURL("image/png");
  link.click();
  hud.toast("Saved");
}

function clear() {
  hud.toast(board.clear() ? "Board cleared · Z to undo" : "Nothing to clear");
}

function cycleView() {
  const view =
    VIEWS[(VIEWS.indexOf(boardElement.dataset.view) + 1) % VIEWS.length];
  boardElement.dataset.view = view;
  hud.toast(`View: ${view}`);
}

const KEYS = {
  z: () => hud.toast(board.undo() ? "Undo" : "Nothing to undo"),
  y: () => hud.toast(board.redo() ? "Redo" : "Nothing to redo"),
  c: clear,
  s: save,
  v: cycleView,
};

COLOURS.forEach((_, index) => (KEYS[index + 1] = () => pickColour(index)));

// Space mode's pen (preventDefault: Space would otherwise scroll, or press a focused button)
for (const [type, held] of [
  ["keydown", true],
  ["keyup", false],
]) {
  document.addEventListener(type, (event) => {
    if (event.key !== " ") return;
    event.preventDefault();
    controls.spaceHeld = held;
  });
}
window.addEventListener("blur", () => (controls.spaceHeld = false)); // Its keyup would go to another window

document.addEventListener("keydown", (event) => {
  if (event.ctrlKey || event.metaKey || event.altKey) return; // Leave the browser's own shortcuts alone
  const action = KEYS[event.key.toLowerCase()];
  if (action === undefined) return;
  event.preventDefault();
  action();
});

// The toolbar's buttons do the same as their keys
for (const button of document.querySelectorAll("#actions [data-key]")) {
  button.addEventListener("click", KEYS[button.dataset.key]);
}

streamFrames(video, onFrame, (text) => (element("stats").textContent = text));
