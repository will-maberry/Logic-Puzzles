/* 
Tents Game Front-End
*/

// Configuration and game state
const tentsApi = "/api/tents";
const tentsSaveKey = "tentsGameSave";

// Saved game lifetime
const tentsSaveLifetimeMs = 30 * 60 * 1000;

// Board sizes for different difficulties
const tentsPresets = {easy: [5, 6, 7], medium: [8, 9, 10], hard: [12, 13, 14, 15]};

// Minimum number of tents per board size
const tentFloors = {
  4: 4, 5: 7, 6: 9, 7: 12, 8: 15, 9: 20, 10: 22,
  11: 27, 12: 31, 13: 36, 14: 42, 15: 48
};

let tentsLevel = "easy";
let tentsPuzzle = null;
let tentsBoard = [];
let tentsNotes = [];
let tentsFinished = false;

// Increment when asynchronous game stat changes
let tentsVersion = 0;

// Track right-button drag
let tentMarkDrag = null;

/*
Status and API
*/


// Display game-status message below board
function tentsStatus(message) {
  document.getElementById("status").textContent = message;
}

// Send JSON to tents API endpoint and return decoded response
  // HTTP errors converted into errors carrying response status to display to player
async function tentsPost(path, payload) {
  const response = await fetch(`${tentsApi}${path}`, {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    const error = new Error("API request failed");
    error.status = response.status;
    throw error;
  }
  return response.json();
}

// Convert API failure into player-facing status message
// Convert API failure into player-facing status message
function tentsApiError(error, action) {
  if (error?.status === 429) {
    return "Too many requests. Try again in a minute.";
  }

  if (error?.status === 404 || error?.status === 405) {
    return "Puzzle API route unavailable. Run the current FastAPI app.";
  }

  return `The API could not ${action}. Try again.`;
}

/*
Board Rendering
*/

function treeKeys() {
  return new Set(tentsPuzzle.trees.map(([row, col]) => `${row},${col}`));
}

function svgNode(tag, attributes) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) node.setAttribute(key, String(value));
  return node;
}

// Render curernt game board as SVG
function drawTents(conflicts = []) {
  const board = document.getElementById("board");
  board.replaceChildren();
  if (!tentsPuzzle) return;

  const size = tentsPuzzle.size;
  const offset = 64;
  const side = (800 - offset) / size;
  const trees = treeKeys();
  const conflictCells = new Set(conflicts.map(([row, col]) => `${row},${col}`));

  // Draw column clues above board
  for (let col = 0; col < size; col++) {
    const label = svgNode("text", {x: offset + (col + 0.5) * side, y: 39,
      "text-anchor": "middle", "font-family": "monospace", "font-size": 28,
      "font-weight": 700, class: "tent-clue"});
    label.style.fill = "var(--ink)";
    label.textContent = tentsPuzzle.col_clues[col];
    board.appendChild(label);
  }

  // Draw row clues followed by interactive board cells
  for (let row = 0; row < size; row++) {
    const label = svgNode("text", {x: 32, y: offset + (row + 0.5) * side + 9,
      "text-anchor": "middle", "font-family": "monospace", "font-size": 28,
      "font-weight": 700, class: "tent-clue"});
    
    label.style.fill = "var(--ink)";
    label.textContent = tentsPuzzle.row_clues[row];

    board.appendChild(label);

    for (let col = 0; col < size; col++) {
      const key = `${row},${col}`;
      const isTree = trees.has(key);

      const cell = svgNode("rect", {
        x: offset + col * side, y: offset + row * side,
        width: side, height: side,
        class: conflictCells.has(key) ? "tent-cell tent-conflict" : "tent-cell",
        "stroke-width": 1, role: "button",
        "aria-label": `Row ${row + 1}, column ${col + 1}${isTree ? ", tree" : ""}`
      });

      cell.style.fill = conflictCells.has(key) ? "lightcoral" : "rgb(131, 164, 125)";

      cell.style.stroke = "#567052";

      cell.dataset.row = String(row);
      cell.dataset.col = String(col);

      // Left-click toggles tent and tents replace notes
      cell.addEventListener("click", () => {
        if (tentsFinished || isTree) return;
        tentsBoard[row][col] = tentsBoard[row][col] ? 0 : 1;
        tentsNotes[row][col] = 0;
        checkTents();
      });

      board.appendChild(cell);

      // Marks are rendered as SVG image over cell
      const icon = isTree ? "tree.svg" : tentsBoard[row][col] ? "campground.svg" : tentsNotes[row][col] ? "xmark.svg" : null;
      
      if (icon) {
        const iconSize = side * (icon === "xmark.svg" ? 0.36 : 0.58);

        const mark = svgNode("image", {
          x: offset + col * side + (side - iconSize) / 2,
          y: offset + row * side + (side - iconSize) / 2,
          width: iconSize, height: iconSize, href: `/static/icons/${icon}`
        });

        mark.style.filter = "none";
        board.appendChild(mark);
      }
    }
  }
}

// Paint X marks
function paintTentMark(row, col) {
  if (!tentMarkDrag || !tentsPuzzle || tentsFinished ||
      row < 0 || col < 0 || row >= tentsPuzzle.size || col >= tentsPuzzle.size) return;
  
  const key = `${row},${col}`;

  // Each cell changed at most once per drag
    // cells with trees and tents can't receive X
  if (tentMarkDrag.visited.has(key) || treeKeys().has(key) || tentsBoard[row][col]) return;

  tentMarkDrag.visited.add(key);
  tentsNotes[row][col] = tentMarkDrag.value;

  drawTents();
}

// New puzzle function
async function newTents(discardSave = false) {
  const sizes = tentsPresets[tentsLevel];
  const size = sizes[Math.floor(Math.random() * sizes.length)];

  // Capture request version so it's response can be ignored if palyer starts another puzzle before generation complete
  const version = ++tentsVersion;

  tentsStatus("Generating puzzle...");

  try {
    const puzzle = await tentsPost("/generate", {size});
    if (version !== tentsVersion) return;
    let clearFailed = false;
    if (discardSave) {
      try { localStorage.removeItem(tentsSaveKey); }
      catch (_) { clearFailed = true; }
    }

    tentsPuzzle = puzzle;
    tentsBoard = Array.from({length: size}, () => Array(size).fill(0));
    tentsNotes = Array.from({length: size}, () => Array(size).fill(0));

    tentsFinished = false;

    document.getElementById("puzzleMeta").textContent = `${size}×${size} BOARD · ${puzzle.trees.length} TENTS`;
    
    drawTents();

    tentsStatus(clearFailed ? "New puzzle loaded, but browser storage could not be cleared." : "Place one tent beside each tree.");
  } catch (error) {
    if (version === tentsVersion) tentsStatus(tentsApiError(error, "generate a puzzle"));
  }
}

// Set tents game difficulty
function syncTentsDifficulty() {
  document.querySelectorAll(".difficulty-options [data-level]").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.level === tentsLevel));
  });
}

// Game board validation
async function checkTents() {
  if (!tentsPuzzle) return;

  // Each move invalidates and check mid-computation
  const version = ++tentsVersion;

  drawTents();
  tentsStatus("Checking...");

  try {
    const {size, trees, row_clues, col_clues} = tentsPuzzle;
    const result = await tentsPost("/check", {size, trees, row_clues, col_clues, board: tentsBoard});

    // Ignore checks from old state
    if (version !== tentsVersion) return;

    if (result.win && !tentsFinished) celebrateBoard(document.querySelector(".board-frame"));

    tentsFinished = result.win;

    drawTents(result.conflicts);

    tentsStatus(result.win ? "Solved!" : result.conflicts.length ? "Tent conflicts detected." : "Keep going.");
  } catch (error) {
    if (version === tentsVersion) tentsStatus(tentsApiError(error, "check this move"));
  }
}

// Reveal puzzle solution
function revealTents() {
  if (!tentsPuzzle) return;

  if (!Array.isArray(tentsPuzzle.solution)) {
    tentsStatus("The solution is unavailable for this saved puzzle.");
    return;
  }

  // Invalidate API responses before replacing board
  ++tentsVersion;

  const size = tentsPuzzle.size;

  tentsBoard = Array.from({length: size}, () => Array(size).fill(0));

  for (const [row, col] of tentsPuzzle.solution) tentsBoard[row][col] = 1;

  tentsFinished = true;

  drawTents();
  tentsStatus("Solution revealed.");
}

// Local save and load
function saveTents() {
  if (!tentsPuzzle) { tentsStatus("Load a puzzle before saving."); return; }

  try {
    localStorage.setItem(tentsSaveKey, JSON.stringify({
      timestamp: Date.now(), puzzle: tentsPuzzle, board: tentsBoard,
      notes: tentsNotes, finished: tentsFinished, level: tentsLevel
    }));

    tentsStatus("Game saved in this browser for 30 minutes.");

  } catch (_) { tentsStatus("Browser storage is unavailable."); }
}

// See if matrix is valid dimensions and correctly formatted
function matrixValid(matrix, size) {
  return Array.isArray(matrix) && matrix.length === size && matrix.every(row =>
    Array.isArray(row) && row.length === size && row.every(value => value === 0 || value === 1));
}

function validTentsSave(saved) {
  if (!saved || typeof saved !== "object" || !saved.puzzle) return false;

  const {size, trees, row_clues, col_clues, solution} = saved.puzzle;

  // Validate basec dimensions and binary board state
  if (!Number.isInteger(size) || size < 4 || size > 15 ||
      !matrixValid(saved.board, size) || !matrixValid(saved.notes, size)) return false;
    
  const coordsValid = list => Array.isArray(list) && list.every(pair =>
    Array.isArray(pair) && pair.length === 2 && pair.every(v => Number.isInteger(v) && v >= 0 && v < size));
  
  // Tree and solution coordinates must be valid
  if (!coordsValid(trees) || trees.length < tentFloors[size] ||
      new Set(trees.map(pair => pair.join(","))).size !== trees.length ||
      !coordsValid(solution) || solution.length !== trees.length) return false;
    
  // Row and column clues must match board dimensions
  if (![row_clues, col_clues].every(list => Array.isArray(list) && list.length === size &&
      list.every(value => Number.isInteger(value) && value >= 0 && value <= (size + 1) / 2) &&
      list.reduce((a, b) => a + b, 0) === trees.length)) return false;
  
  const treeSet = new Set(trees.map(pair => pair.join(",")));

  // Saved player marks can't be in tree cells
  if (trees.some(([row, col]) => saved.board[row][col] || saved.notes[row][col]) ||
      solution.some(pair => treeSet.has(pair.join(",")))) return false;
  
  // Reject old saves outside lifetime
  return Number.isFinite(saved.timestamp) && saved.timestamp <= Date.now() &&
    Date.now() - saved.timestamp <= tentsSaveLifetimeMs;
}

// Load tents
function loadTents() {
  let saved;

  try {
    const raw = localStorage.getItem(tentsSaveKey);

    if (!raw) { tentsStatus("No saved game found."); return; }

    // Don't load arbitrarily large saves
    if (raw.length > 50000) throw new Error("Saved game is too large");

    saved = JSON.parse(raw);

  } catch (_) { tentsStatus("Saved game could not be read."); return; }

  // Expired saves removed
  if (saved && Number.isFinite(saved.timestamp) && Date.now() - saved.timestamp > tentsSaveLifetimeMs) {
    try { localStorage.removeItem(tentsSaveKey); } catch (_) {}
    tentsStatus("Saved game expired.");
    return;
  }

  if (!validTentsSave(saved)) { tentsStatus("Saved game is invalid or has expired."); return; }

  // Loading replaces active game, so invalidate pending API requests
  ++tentsVersion;

  tentsPuzzle = saved.puzzle;
  tentsBoard = saved.board;
  tentsNotes = saved.notes;
  tentsFinished = Boolean(saved.finished);

  tentsLevel = Object.hasOwn(tentsPresets, saved.level) ? saved.level : "easy";

  syncTentsDifficulty();

  document.getElementById("puzzleMeta").textContent = `${tentsPuzzle.size}×${tentsPuzzle.size} BOARD · ${tentsPuzzle.trees.length} TENTS`;

  drawTents();

  // Check restored state with server instead of trusting localStorage
  tentsStatus("Saved game loaded. Checking with the API...");
  checkTents();
}

/*
Event Handlers
*/

document.addEventListener("DOMContentLoaded", () => {
  const board = document.getElementById("board");

  // Right-click for X marks and stop default action
  board.addEventListener("contextmenu", event => event.preventDefault());

  // Start painting or removing X marks
  board.addEventListener("pointerdown", event => {
    if (event.button !== 2 || !tentsPuzzle || tentsFinished) return;

    const cell = event.target.closest("rect[data-row][data-col]");

    if (!cell) return;

    event.preventDefault();

    const row = Number(cell.dataset.row), col = Number(cell.dataset.col);

    tentMarkDrag = {value: tentsNotes[row][col] ? 0 : 1, visited: new Set()};
    paintTentMark(row, col);
  });

  // Continue painting as long as right-click pressed
  document.addEventListener("pointermove", event => {
    if (!tentMarkDrag) return;

    if (!(event.buttons & 2)) { tentMarkDrag = null; return; }

    const cell = document.elementFromPoint(event.clientX, event.clientY)?.closest("rect[data-row][data-col]");
    
    if (cell && board.contains(cell)) paintTentMark(Number(cell.dataset.row), Number(cell.dataset.col));
  });

  // Terminate drag when pointer released
  document.addEventListener("pointerup", () => { tentMarkDrag = null; });
  window.addEventListener("blur", () => { tentMarkDrag = null; });

  // Game controls
  document.getElementById("newPuzzle").addEventListener("click", () => newTents(true));
  document.getElementById("saveGame").addEventListener("click", saveTents);
  document.getElementById("loadGame").addEventListener("click", loadTents);
  document.getElementById("revealSolution").addEventListener("click", revealTents);

  // Changing difficulty causes new puzzle to be generated
  document.querySelectorAll(".difficulty-options [data-level]").forEach(button => {
    button.addEventListener("click", () => {
      if (!Object.hasOwn(tentsPresets, button.dataset.level)) return;

      tentsLevel = button.dataset.level;

      syncTentsDifficulty();
      newTents(true);
    });
  });

  // Help modal
  const modal = document.getElementById("helpModal");

  document.getElementById("helpButton").addEventListener("click", () => { modal.style.display = "block"; });

  document.getElementById("closeHelp").addEventListener("click", () => { modal.style.display = "none"; });

  modal.addEventListener("click", event => { if (event.target === modal) modal.style.display = "none"; });

  document.addEventListener("keydown", event => { if (event.key === "Escape") modal.style.display = "none"; });

  // Always generate new puzzle on page load
  newTents();
});