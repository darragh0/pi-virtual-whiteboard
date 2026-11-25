// The virtual whiteboard: the Pi's video, with what the hand draws on top

import { Board } from "./board.js";
import { Controls } from "./controls.js";
import { Hud } from "./hud.js";
import { streamFrames } from "./stream.js";

const VIEWS = ["dim", "camera", "board"]; // Behind the ink: the video dimmed, as is, or hidden
const SAVE_BACKGROUND = "#000";

const element = (id) => document.getElementById(id);
const boardElement = element("board");
const video = element("video");
const ink = element("ink");

const board = new Board(ink);
const hud = new Hud({ cursor: element("cursor"), toast: element("toast") });
const controls = new Controls(board, hud);
const gestureChips = document.querySelectorAll("#gestures [data-gesture]");

function onFrame(hand) {
  boardElement.style.setProperty("--aspect", video.naturalWidth / video.naturalHeight);
  controls.update(hand, performance.now());

  for (const chip of gestureChips) chip.classList.toggle("active", chip.dataset.gesture === hand.gesture);
  element("colour").style.background = controls.colour.value;
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

function cycleView() {
  const view = VIEWS[(VIEWS.indexOf(boardElement.dataset.view) + 1) % VIEWS.length];
  boardElement.dataset.view = view;
  hud.toast(`View: ${view}`);
}

const KEYS = {
  z: () => hud.toast(board.undo() ? "Undo" : "Nothing to undo"),
  y: () => hud.toast(board.redo() ? "Redo" : "Nothing to redo"),
  c: () => controls.clear(),
  s: save,
  v: cycleView,
};

document.addEventListener("keydown", (event) => {
  if (event.ctrlKey || event.metaKey || event.altKey) return; // Leave the browser's own shortcuts alone
  const action = KEYS[event.key.toLowerCase()];
  if (action === undefined) return;
  event.preventDefault();
  action();
});

streamFrames(video, onFrame, (text) => (element("stats").textContent = text));
